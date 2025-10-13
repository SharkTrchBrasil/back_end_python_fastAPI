# src/api/admin/routes/stores.py
import asyncio
import re
import uuid
from datetime import datetime, timedelta, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status, Response, UploadFile, Form, File
from sqlalchemy import func

from src.api.admin.services.cloning_service import clone_store_data
from src.api.admin.socketio.emitters import admin_emit_store_updated, admin_emit_stores_list_update
from src.api.app.socketio.socketio_emitters import emit_store_updated
from src.api.schemas.auth.store_access import StoreAccess
from src.api.schemas.auth.user import CreateStoreUserRequest, GrantStoreAccessRequest
from src.api.schemas.store.store import Store
from src.api.schemas.store.store_details import StoreDetails
from src.api.schemas.store.store_with_role import StoreWithRole
from src.core import models
from src.core.aws import delete_file, upload_single_file
from src.core.database import GetDBDep
from src.core.defaults.delivery_methods import default_delivery_settings
from src.core.dependencies import GetCurrentUserDep, GetStoreDep, GetStore
from src.core.security import get_password_hash
from src.core.utils.enums import StoreVerificationStatus, Roles
from src.core.utils.referral import generate_unique_referral_code

router = APIRouter(prefix="/stores", tags=["Stores"])

ALLOWED_ROLES_FOR_CREATION = ['manager', 'cashier', 'waiter', 'stock_manager']


@router.post("", response_model=StoreWithRole)
async def create_store(
        db: GetDBDep,
        user: GetCurrentUserDep,
        name: str = Form(...),
        store_url: str = Form(...),
        phone: str = Form(...),
        description: str | None = Form(None),
        cnpj: str | None = Form(None),
        segment_id: int = Form(...),
        cep: str = Form(...),
        street: str = Form(...),
        number: str = Form(...),
        complement: str | None = Form(None),
        neighborhood: str = Form(...),
        city: str = Form(...),
        uf: str = Form(...),
        responsible_name: str = Form(...),
        responsible_phone: str = Form(...),
):
    """Cria uma nova loja com configurações padrão e trial de 30 dias."""

    if cnpj:
        existing_store_by_cnpj = db.query(models.Store).filter(models.Store.cnpj == cnpj).first()
        if existing_store_by_cnpj:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="O CNPJ informado já está cadastrado em outra loja."
            )

    if phone:
        existing_user_by_phone = db.query(models.User).filter(
            models.User.phone == phone,
            models.User.id != user.id
        ).first()
        if existing_user_by_phone:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="O telefone do responsável já está associado a outra conta."
            )

    db_store = models.Store(
        name=name, phone=phone, url_slug=store_url, description=description,
        segment_id=segment_id, cnpj=cnpj, zip_code=cep, street=street, number=number,
        complement=complement, neighborhood=neighborhood, city=city, state=uf,
        responsible_name=responsible_name, responsible_phone=responsible_phone,
        is_active=True, is_setup_complete=False,
        verification_status=StoreVerificationStatus.UNVERIFIED
    )
    db.add(db_store)
    db.flush()

    default_saloon = models.Saloon(store_id=db_store.id, name="Salão Principal")
    db.add(default_saloon)
    db.flush()

    default_tables = [
        models.Tables(
            store_id=db_store.id,
            saloon_id=default_saloon.id,
            name=f"Mesa {i:02d}",
            max_capacity=4
        ) for i in range(1, 11)
    ]
    db.add_all(default_tables)

    all_templates = db.query(models.ChatbotMessageTemplate).all()
    for template in all_templates:
        is_active_default = template.message_key != 'loyalty_program'
        new_store_message_config = models.StoreChatbotMessage(
            store_id=db_store.id,
            template_key=template.message_key,
            is_active=is_active_default
        )
        db.add(new_store_message_config)

    default_payment_methods = db.query(models.PlatformPaymentMethod).filter(
        models.PlatformPaymentMethod.is_default_for_new_stores == True
    ).all()

    new_store_payment_activations = [
        models.StorePaymentMethodActivation(
            store_id=db_store.id,
            platform_payment_method_id=platform_method.id,
            is_active=True
        ) for platform_method in default_payment_methods
    ]

    if new_store_payment_activations:
        db.add_all(new_store_payment_activations)

    db_store_configuration = models.StoreOperationConfig(
        store_id=db_store.id,
        is_store_open=True,
        auto_accept_orders=False,
        auto_print_orders=False,
        **default_delivery_settings
    )
    db.add(db_store_configuration)

    totem_token = str(uuid.uuid4())
    totem_auth = models.TotemAuthorization(
        store_id=db_store.id, totem_token=totem_token, public_key=totem_token,
        totem_name=db_store.name, granted=True, granted_by_id=user.id,
        store_url=db_store.url_slug,
    )
    db.add(totem_auth)

    db_role = db.query(models.Role).filter(models.Role.machine_name == "owner").first()
    db_store_access = models.StoreAccess(user=user, role=db_role, store=db_store)
    db.add(db_store_access)

    main_plan = db.query(models.Plans).first()
    if not main_plan:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail="Configuração do sistema: Nenhum plano principal foi encontrado."
        )

    start_date = datetime.now(timezone.utc)
    end_date = start_date + timedelta(days=30)

    store_subscription = models.StoreSubscription(
        store=db_store,
        plan=main_plan,
        status="trialing",
        current_period_start=start_date,
        current_period_end=end_date,
    )
    db.add(store_subscription)

    db.commit()
    db.refresh(db_store_access)

    await admin_emit_stores_list_update(db, admin_user=user)
    await admin_emit_store_updated(db, store_id=db_store.id)

    return db_store_access


@router.post("/clone", response_model=StoreWithRole, status_code=status.HTTP_201_CREATED)
async def clone_store(
        db: GetDBDep,
        user: GetCurrentUserDep,
        source_store_id: int = Form(...),
        name: str = Form(...),
        url_slug: str = Form(...),
        phone: str = Form(...),
        description: str | None = Form(None),
        address_json: str = Form(..., alias="address"),
        options_json: str = Form(..., alias="options"),
):
    """Cria uma nova loja clonando dados de uma loja existente."""
    import json
    address = json.loads(address_json)
    options = json.loads(options_json)

    source_store_access = db.query(models.StoreAccess).filter(
        models.StoreAccess.store_id == source_store_id,
        models.StoreAccess.user_id == user.id
    ).first()

    if not source_store_access:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Loja de origem não encontrada ou você não tem permissão para acessá-la."
        )

    source_store = source_store_access.store

    existing_by_url = db.query(models.Store).filter(models.Store.url_slug == url_slug).first()
    if existing_by_url:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A URL informada já está em uso."
        )

    new_store = models.Store(
        name=name,
        url_slug=url_slug,
        phone=phone,
        description=description,
        segment_id=source_store.segment_id,
        zip_code=address.get('cep'),
        street=address.get('street'),
        number=address.get('number'),
        complement=address.get('complement'),
        neighborhood=address.get('neighborhood'),
        city=address.get('city'),
        state=address.get('uf'),
        responsible_name=user.name,
        responsible_phone=user.phone,
        is_active=True,
        is_setup_complete=False,
        verification_status=StoreVerificationStatus.UNVERIFIED
    )
    db.add(new_store)
    db.flush()

    if not options.get('operation_config', False):
        db_store_configuration = models.StoreOperationConfig(
            store_id=new_store.id,
            is_store_open=True,
            **default_delivery_settings
        )
        db.add(db_store_configuration)

    clone_store_data(db, source_store_id=source_store.id, new_store_id=new_store.id, options=options)

    owner_role = db.query(models.Role).filter(models.Role.machine_name == "owner").first()
    new_access = models.StoreAccess(user=user, role=owner_role, store=new_store)
    db.add(new_access)

    main_plan = db.query(models.Plans).first()
    if not main_plan:
        db.rollback()
        raise HTTPException(status_code=500, detail="Configuração de plano principal não encontrada.")

    start_date = datetime.now(timezone.utc)
    end_date = start_date + timedelta(days=30)

    new_subscription = models.StoreSubscription(
        store=new_store,
        plan=main_plan,
        status="trialing",
        current_period_start=start_date,
        current_period_end=end_date,
    )
    db.add(new_subscription)

    db.commit()
    db.refresh(new_access)

    await admin_emit_stores_list_update(db, admin_user=user)
    await admin_emit_store_updated(db, store_id=new_store.id)

    return new_access


@router.get("", response_model=list[StoreWithRole])
def list_stores(db: GetDBDep, user: GetCurrentUserDep):
    """Retorna todas as lojas acessíveis pelo usuário."""
    db_store_accesses = db.query(models.StoreAccess).filter(
        models.StoreAccess.user == user
    ).all()

    return [StoreWithRole.model_validate(access) for access in db_store_accesses]


@router.get("/{store_id}", response_model=StoreDetails)
def get_store(store: Annotated[Store, Depends(GetStore([Roles.OWNER]))]):
    """Retorna os detalhes completos de uma loja."""
    return store


@router.patch("/{store_id}", response_model=StoreDetails)
async def patch_store(
        db: GetDBDep,
        store: Annotated[Store, Depends(GetStore([Roles.OWNER]))],
        name: str | None = Form(None),
        phone: str | None = Form(None),
        email: str | None = Form(None),
        site: str | None = Form(None),
        instagram: str | None = Form(None),
        facebook: str | None = Form(None),
        tiktok: str | None = Form(None),
        whatsapp: str | None = Form(None),
        about: str | None = Form(None),
        cnpj: str | None = Form(None),
        zip_code: str | None = Form(None),
        street: str | None = Form(None),
        number: str | None = Form(None),
        neighborhood: str | None = Form(None),
        complement: str | None = Form(None),
        reference: str | None = Form(None),
        city: str | None = Form(None),
        state: str | None = Form(None),
        description: str | None = Form(None),
        image: UploadFile | None = File(None),
        banner: UploadFile | None = File(None),
        url_slug: str | None = Form(None),
        segment_id: int | None = Form(None),
        responsible_name: str | None = Form(None),
        responsible_phone: str | None = Form(None),
        is_setup_complete: bool | None = Form(None),
):
    """Atualiza as informações de uma loja."""
    file_key_to_delete = None
    if image:
        file_key_to_delete = store.file_key
        store.file_key = upload_single_file(image)

    banner_key_to_delete = None
    if banner:
        banner_key_to_delete = store.banner_file_key
        store.banner_file_key = upload_single_file(banner)

    update_data = {
        "name": name, "phone": phone, "description": description,
        "url_slug": url_slug, "cnpj": cnpj, "segment_id": segment_id,
        "zip_code": zip_code, "street": street, "number": number,
        "neighborhood": neighborhood, "complement": complement, "city": city, "state": state,
        "responsible_name": responsible_name, "responsible_phone": responsible_phone,
        "is_setup_complete": is_setup_complete,
    }

    for key, value in update_data.items():
        if value is not None:
            setattr(store, key, value)

    db.add(store)
    db.commit()
    db.refresh(store)

    if file_key_to_delete:
        delete_file(file_key_to_delete)
    if banner_key_to_delete:
        delete_file(banner_key_to_delete)

    await asyncio.create_task(emit_store_updated(db, store.id))
    await admin_emit_store_updated(db, store.id)
    return store


@router.post(
    "/{store_id}/accesses",
    response_model=StoreAccess,
    status_code=status.HTTP_201_CREATED,
    summary="Criar novo usuário e vinculá-lo à loja"
)
async def create_user_for_store(
        db: GetDBDep,
        store: GetStoreDep,
        user_data: CreateStoreUserRequest,
        current_user: GetCurrentUserDep,
):
    """
    Cria um novo usuário no sistema e concede acesso à loja especificada.

    - Valida todos os dados de entrada
    - Verifica duplicatas de e-mail e telefone
    - Cria o usuário com senha criptografada
    - Vincula o usuário à loja com a função especificada
    """

    # ✅ 1. VALIDAÇÃO DA FUNÇÃO (ROLE)
    role = db.query(models.Role).filter(
        models.Role.machine_name == user_data.role_machine_name
    ).first()

    if not role:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"A função '{user_data.role_machine_name}' não foi encontrada no sistema."
        )

    if user_data.role_machine_name not in ALLOWED_ROLES_FOR_CREATION:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Não é permitido criar usuários com a função '{user_data.role_machine_name}'."
        )

    # ✅ 2. NORMALIZAÇÃO E VALIDAÇÃO DO E-MAIL
    normalized_email = user_data.email.strip().lower()

    existing_user = db.query(models.User).filter(
        func.lower(models.User.email) == normalized_email
    ).first()

    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Um usuário com o e-mail '{user_data.email}' já está cadastrado no sistema."
        )

    # ✅ 3. LIMPEZA E VALIDAÇÃO DO TELEFONE
    phone_clean = re.sub(r'\D', '', user_data.phone)

    if len(phone_clean) < 10 or len(phone_clean) > 11:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="O telefone deve ter 10 ou 11 dígitos."
        )

    # ✅ 4. VERIFICAÇÃO DE TELEFONE DUPLICADO
    existing_phone = db.query(models.User).filter(
        models.User.phone == phone_clean
    ).first()

    if existing_phone:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"O telefone '{user_data.phone}' já está cadastrado no sistema."
        )

    # ✅ 5. VALIDAÇÃO DA SENHA
    if len(user_data.password) < 6:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A senha deve ter no mínimo 6 caracteres."
        )

    # ✅ 6. VALIDAÇÃO DO NOME
    name_clean = user_data.name.strip()

    if len(name_clean) < 3:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="O nome deve ter no mínimo 3 caracteres."
        )

    # ✅ 7. CRIAÇÃO DO USUÁRIO COM TRATAMENTO DE ERRO
    try:
        hashed_password = get_password_hash(user_data.password)

        # ✅ IMPORTAÇÃO NECESSÁRIA: from src.core.utils.referral import generate_unique_referral_code
        new_user = models.User(
            email=normalized_email,
            name=name_clean,
            phone=phone_clean,
            hashed_password=hashed_password,
            is_active=True,
            referral_code=generate_unique_referral_code(db, name_clean),
            is_store_owner=False,
            is_email_verified=True,
            referred_by_user_id=None
        )

        db.add(new_user)
        db.flush()  # ✅ CRUCIAL: Garante que o ID seja gerado antes de prosseguir

    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro ao criar o usuário: {str(e)}"
        )

    # ✅ 8. CRIAÇÃO DO ACESSO À LOJA COM TRATAMENTO DE ERRO
    try:
        new_access = models.StoreAccess(
            user=new_user,
            store=store,
            role=role
        )

        db.add(new_access)
        db.commit()
        db.refresh(new_access)

    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro ao criar o acesso à loja: {str(e)}"
        )

    # ✅ 9. RETORNO DO ACESSO CRIADO
    return new_access








@router.get("/{store_id}/accesses", response_model=list[StoreAccess])
def get_store_accesses(db: GetDBDep, store: GetStoreDep):
    """Lista todos os usuários com acesso à loja."""
    store_accesses = db.query(models.StoreAccess).filter(
        models.StoreAccess.store_id == store.id
    ).all()
    return store_accesses


@router.put(
    "/{store_id}/accesses",
    response_model=StoreAccess,
    summary="Convidar usuário existente ou atualizar role"
)
def grant_or_update_store_access(
        db: GetDBDep,
        store: GetStoreDep,
        access_data: GrantStoreAccessRequest,
        current_user: GetCurrentUserDep,
):
    """Concede acesso à loja para um usuário existente ou atualiza sua função."""

    if current_user.email.lower() == access_data.user_email.lower():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Você não pode alterar sua própria função na loja."
        )

    role = db.query(models.Role).filter(
        models.Role.machine_name == access_data.role_machine_name
    ).first()

    if not role:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"A função '{access_data.role_machine_name}' não foi encontrada."
        )

    if access_data.role_machine_name == 'owner':
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Não é permitido atribuir a função 'owner' via esta rota."
        )

    target_user = db.query(models.User).filter(
        func.lower(models.User.email) == access_data.user_email.lower()
    ).first()

    if not target_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Nenhum usuário encontrado com o e-mail '{access_data.user_email}'."
        )

    existing_access = db.query(models.StoreAccess).filter(
        models.StoreAccess.store_id == store.id,
        models.StoreAccess.user_id == target_user.id
    ).first()

    if existing_access:
        if existing_access.role.machine_name == 'owner':
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Não é permitido alterar a função de um proprietário."
            )

        existing_access.role = role
        db.commit()
        db.refresh(existing_access)

        return existing_access

    else:
        new_access = models.StoreAccess(
            user=target_user,
            store=store,
            role=role
        )

        db.add(new_access)
        db.commit()
        db.refresh(new_access)

        return new_access


@router.delete("/{store_id}/accesses")
def delete_store_access(
        db: GetDBDep,
        store: GetStoreDep,
        user_id: int,
        user: GetCurrentUserDep,
):
    """Remove o acesso de um usuário à loja."""
    if user.id == user_id:
        raise HTTPException(
            status_code=400,
            detail="Você não pode remover seu próprio acesso."
        )

    store_access = db.query(models.StoreAccess).filter(
        models.StoreAccess.store_id == store.id,
        models.StoreAccess.user_id == user_id
    ).first()

    if store_access is None:
        raise HTTPException(
            status_code=400,
            detail="Acesso não encontrado."
        )

    db.delete(store_access)
    db.commit()


@router.get(
    "/check-url/{url_slug}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Verificar disponibilidade de URL"
)
def check_url_availability(url_slug: str, db: GetDBDep):
    """Verifica se uma URL de loja está disponível."""
    existing_store = db.query(models.Store).filter(
        func.lower(models.Store.url_slug) == url_slug.lower()
    ).first()

    if existing_store:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Esta URL já está em uso por outra loja."
        )

    return Response(status_code=status.HTTP_204_NO_CONTENT)