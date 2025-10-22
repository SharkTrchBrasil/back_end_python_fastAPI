# src/api/admin/routes/stores.py
import asyncio
import re
import uuid
from datetime import datetime, timedelta, timezone
from sqlite3 import IntegrityError
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status, Response, UploadFile, Form, File
from sqlalchemy import func
from starlette.requests import Request

from src.api.admin.services.cloning_service import clone_store_data
from src.api.admin.services.subscription_service import SubscriptionService
from src.api.admin.socketio.emitters import admin_emit_store_updated, admin_emit_stores_list_update, emit_store_updates
from src.api.app.socketio.socketio_emitters import emit_store_updated
from src.api.schemas.auth.store_access import StoreAccess
from src.api.schemas.auth.user import CreateStoreUserRequest, GrantStoreAccessRequest
from src.api.schemas.store.store import Store, StoreSchema
from src.api.schemas.store.store_details import StoreDetails
from src.api.schemas.store.store_with_role import StoreWithRole
from src.core import models
from src.core.aws import delete_file, upload_single_file
from src.core.database import GetDBDep
from src.core.defaults.delivery_methods import default_delivery_settings
from src.core.dependencies import GetCurrentUserDep, GetStoreDep, GetStore, GetAuditLoggerDep  # ✅ ADICIONAR
from src.core.rate_limit.rate_limit import RATE_LIMITS, limiter
from src.core.security.security import get_password_hash
from src.core.utils.enums import StoreVerificationStatus, Roles, AuditAction, AuditEntityType  # ✅ ADICIONAR
from src.core.utils.referral import generate_unique_referral_code

router = APIRouter(prefix="/stores", tags=["Stores"])

ALLOWED_ROLES_FOR_CREATION = ['manager', 'cashier', 'waiter', 'stock_manager']


# ===================================================================
# 🔥 PONTO VITAL 1: CRIAÇÃO DE LOJA
# ===================================================================
@router.post("", response_model=StoreWithRole)
@limiter.limit(RATE_LIMITS["write"])
async def create_store(
        request: Request,
        db: GetDBDep,
        user: GetCurrentUserDep,
        audit: GetAuditLoggerDep,  # ✅ ADICIONAR AUDITORIA
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
        # ✅ NOVOS PARÂMETROS ADICIONADOS
        latitude: float | None = Form(None),
        longitude: float | None = Form(None),
        delivery_radius_km: float | None = Form(None),
):
    """Cria uma nova loja com configurações padrão e trial de 30 dias."""

    if cnpj:
        existing_store_by_cnpj = db.query(models.Store).filter(models.Store.cnpj == cnpj).first()
        if existing_store_by_cnpj:
            # ✅ LOG DE TENTATIVA FALHADA
            audit.log_failed_action(
                action=AuditAction.CREATE_STORE,
                entity_type=AuditEntityType.STORE,
                error=f"CNPJ duplicado: {cnpj}"
            )
            db.commit()
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
            # ✅ LOG DE TENTATIVA FALHADA
            audit.log_failed_action(
                action=AuditAction.CREATE_STORE,
                entity_type=AuditEntityType.STORE,
                error=f"Telefone duplicado: {phone}"
            )
            db.commit()
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="O telefone do responsável já está associado a outra conta."
            )

    db_store = models.Store(
        name=name, phone=phone, url_slug=store_url, description=description,
        segment_id=segment_id, cnpj=cnpj, zip_code=cep, street=street, number=number,
        complement=complement, neighborhood=neighborhood, city=city, state=uf,
        responsible_name=responsible_name, responsible_phone=responsible_phone,
        latitude=latitude,
        longitude=longitude,
        delivery_radius_km=delivery_radius_km if delivery_radius_km else 10.0,  # Default 10km
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

    # ✅ LOG DE CRIAÇÃO BEM-SUCEDIDA
    audit.log(
        action=AuditAction.CREATE_STORE,
        entity_type=AuditEntityType.STORE,
        entity_id=db_store.id,
        changes={
            "name": name,
            "url_slug": store_url,
            "cnpj": cnpj,
            "city": city,
            "state": uf,
            "segment_id": segment_id,
            "latitude": latitude,
            "longitude": longitude,
            "delivery_radius_km": delivery_radius_km,
            "trial_days": 30,
            "plan_id": main_plan.id
        },
        description=f"Loja '{name}' criada com trial de 30 dias"
    )

    db.commit()
    db.refresh(db_store_access)

    await admin_emit_stores_list_update(db, admin_user=user)
    await emit_store_updates(db, store_id=db_store.id)

    return db_store_access


# ===================================================================
# 🔥 PONTO VITAL 2: CLONAGEM DE LOJA
# ===================================================================
@router.post("/clone", response_model=StoreWithRole, status_code=status.HTTP_201_CREATED)
async def clone_store(
        request: Request,  # ✅ ADICIONAR
        db: GetDBDep,
        user: GetCurrentUserDep,
        audit: GetAuditLoggerDep,  # ✅ ADICIONAR AUDITORIA
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
        # ✅ LOG DE TENTATIVA FALHADA
        audit.log_failed_action(
            action=AuditAction.CREATE_STORE,
            entity_type=AuditEntityType.STORE,
            error=f"Tentativa de clonar loja {source_store_id} sem permissão"
        )
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Loja de origem não encontrada ou você não tem permissão para acessá-la."
        )

    source_store = source_store_access.store

    existing_by_url = db.query(models.Store).filter(models.Store.url_slug == url_slug).first()
    if existing_by_url:
        audit.log_failed_action(
            action=AuditAction.CREATE_STORE,
            entity_type=AuditEntityType.STORE,
            error=f"URL duplicada: {url_slug}"
        )
        db.commit()
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

    # ✅ LOG DE CLONAGEM BEM-SUCEDIDA
    audit.log(
        action=AuditAction.CREATE_STORE,
        entity_type=AuditEntityType.STORE,
        entity_id=new_store.id,
        changes={
            "source_store_id": source_store_id,
            "source_store_name": source_store.name,
            "new_store_name": name,
            "url_slug": url_slug,
            "cloned_options": options
        },
        description=f"Loja '{name}' criada por clonagem de '{source_store.name}'"
    )

    db.commit()
    db.refresh(new_access)

    await admin_emit_stores_list_update(db, admin_user=user)
    await admin_emit_store_updated(db, store_id=new_store.id)

    return new_access


# ===================================================================
# 🔥 PONTO VITAL 3: ATUALIZAÇÃO DE INFORMAÇÕES DA LOJA
# ===================================================================
@router.patch("/{store_id}", response_model=StoreDetails)
async def patch_store(
        request: Request,  # ✅ ADICIONAR
        db: GetDBDep,
        current_user: GetCurrentUserDep,  # ✅ ADICIONAR
        audit: GetAuditLoggerDep,  # ✅ ADICIONAR AUDITORIA
        store: Annotated[Store, Depends(GetStore([Roles.OWNER, Roles.MANAGER]))],
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

    # ✅ CAPTURA O ESTADO ANTERIOR PARA AUDITORIA
    old_values = {}
    changes = {}

    file_key_to_delete = None
    if image:
        old_values["file_key"] = store.file_key
        file_key_to_delete = store.file_key
        store.file_key = upload_single_file(image)
        changes["image_updated"] = True

    banner_key_to_delete = None
    if banner:
        old_values["banner_file_key"] = store.banner_file_key
        banner_key_to_delete = store.banner_file_key
        store.banner_file_key = upload_single_file(banner)
        changes["banner_updated"] = True

    def normalize_empty_string(value: str | None) -> str | None:
        """Converte strings vazias para None (NULL no banco)"""
        if value is None:
            return None
        stripped = value.strip()
        return stripped if stripped else None

    update_data = {
        "name": name,
        "phone": phone,
        "description": description,
        "url_slug": url_slug,
        "cnpj": normalize_empty_string(cnpj),
        "segment_id": segment_id,
        "zip_code": zip_code,
        "street": street,
        "number": number,
        "neighborhood": neighborhood,
        "complement": normalize_empty_string(complement),
        "city": city,
        "state": state,
        "responsible_name": responsible_name,
        "responsible_phone": normalize_empty_string(responsible_phone),
        "is_setup_complete": is_setup_complete,
    }

    # ✅ RASTREIA MUDANÇAS
    for key, value in update_data.items():
        if value is not None:
            old_value = getattr(store, key)
            if old_value != value:
                old_values[key] = old_value
                changes[key] = value
            setattr(store, key, value)

    db.add(store)

    try:
        # ✅ LOG DE ATUALIZAÇÃO BEM-SUCEDIDA
        audit.log(
            action=AuditAction.UPDATE_STORE_SETTINGS,
            entity_type=AuditEntityType.STORE,
            entity_id=store.id,
            changes={
                "old_values": old_values,
                "new_values": changes
            },
            description=f"Informações da loja '{store.name}' atualizadas"
        )

        db.commit()
        db.refresh(store)

    except IntegrityError as e:
        db.rollback()

        # ✅ LOG DE FALHA
        if "ix_stores_cnpj" in str(e):
            audit.log_failed_action(
                action=AuditAction.UPDATE_STORE_SETTINGS,
                entity_type=AuditEntityType.STORE,
                entity_id=store.id,
                error=f"CNPJ duplicado: {cnpj}"
            )
            db.commit()
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={
                    "message": "Este CNPJ já está cadastrado em outra loja.",
                    "code": "DUPLICATE_CNPJ"
                }
            )

        audit.log_failed_action(
            action=AuditAction.UPDATE_STORE_SETTINGS,
            entity_type=AuditEntityType.STORE,
            entity_id=store.id,
            error=str(e)
        )
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "message": "Erro de integridade de dados. Verifique os campos únicos.",
                "code": "INTEGRITY_ERROR"
            }
        )

    if file_key_to_delete:
        delete_file(file_key_to_delete)
    if banner_key_to_delete:
        delete_file(banner_key_to_delete)

    await emit_store_updates(db, store.id)
    return store


# ===================================================================
# 🔥 PONTO VITAL 4: CRIAÇÃO DE NOVO USUÁRIO PARA A LOJA
# ===================================================================
@router.post(
    "/{store_id}/accesses",
    response_model=StoreAccess,
    status_code=status.HTTP_201_CREATED,
    summary="Criar novo usuário e vinculá-lo à loja"
)
async def create_user_for_store(
        request: Request,  # ✅ ADICIONAR
        db: GetDBDep,
        store: GetStoreDep,
        user_data: CreateStoreUserRequest,
        current_user: GetCurrentUserDep,
        audit: GetAuditLoggerDep,  # ✅ ADICIONAR AUDITORIA
):
    """Cria um novo usuário no sistema e concede acesso à loja especificada."""

    role = db.query(models.Role).filter(
        models.Role.machine_name == user_data.role_machine_name
    ).first()

    if not role:
        audit.log_failed_action(
            action=AuditAction.GRANT_STORE_ACCESS,
            entity_type=AuditEntityType.STORE_ACCESS,
            error=f"Função inválida: {user_data.role_machine_name}"
        )
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"A função '{user_data.role_machine_name}' não foi encontrada no sistema."
        )

    if user_data.role_machine_name not in ALLOWED_ROLES_FOR_CREATION:
        audit.log_failed_action(
            action=AuditAction.GRANT_STORE_ACCESS,
            entity_type=AuditEntityType.STORE_ACCESS,
            error=f"Tentativa de criar usuário com função não permitida: {user_data.role_machine_name}"
        )
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Não é permitido criar usuários com a função '{user_data.role_machine_name}'."
        )

    normalized_email = user_data.email.strip().lower()

    existing_user = db.query(models.User).filter(
        func.lower(models.User.email) == normalized_email
    ).first()

    if existing_user:
        audit.log_failed_action(
            action=AuditAction.GRANT_STORE_ACCESS,
            entity_type=AuditEntityType.USER,
            error=f"E-mail duplicado: {user_data.email}"
        )
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Um usuário com o e-mail '{user_data.email}' já está cadastrado no sistema."
        )

    phone_clean = re.sub(r'\D', '', user_data.phone)

    if len(phone_clean) < 10 or len(phone_clean) > 11:
        audit.log_failed_action(
            action=AuditAction.GRANT_STORE_ACCESS,
            entity_type=AuditEntityType.USER,
            error=f"Telefone inválido: {user_data.phone}"
        )
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="O telefone deve ter 10 ou 11 dígitos."
        )

    existing_phone = db.query(models.User).filter(
        models.User.phone == phone_clean
    ).first()

    if existing_phone:
        audit.log_failed_action(
            action=AuditAction.GRANT_STORE_ACCESS,
            entity_type=AuditEntityType.USER,
            error=f"Telefone duplicado: {user_data.phone}"
        )
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"O telefone '{user_data.phone}' já está cadastrado no sistema."
        )

    if len(user_data.password) < 6:
        audit.log_failed_action(
            action=AuditAction.GRANT_STORE_ACCESS,
            entity_type=AuditEntityType.USER,
            error="Senha muito curta"
        )
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A senha deve ter no mínimo 6 caracteres."
        )

    name_clean = user_data.name.strip()

    if len(name_clean) < 3:
        audit.log_failed_action(
            action=AuditAction.GRANT_STORE_ACCESS,
            entity_type=AuditEntityType.USER,
            error="Nome muito curto"
        )
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="O nome deve ter no mínimo 3 caracteres."
        )

    try:
        hashed_password = get_password_hash(user_data.password)

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
        db.flush()

    except Exception as e:
        db.rollback()
        audit.log_failed_action(
            action=AuditAction.GRANT_STORE_ACCESS,
            entity_type=AuditEntityType.USER,
            error=f"Erro ao criar usuário: {str(e)}"
        )
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro ao criar o usuário: {str(e)}"
        )

    try:
        new_access = models.StoreAccess(
            user=new_user,
            store=store,
            role=role
        )

        db.add(new_access)

        # ✅ LOG DE CRIAÇÃO DE ACESSO BEM-SUCEDIDA
        audit.log(
            action=AuditAction.GRANT_STORE_ACCESS,
            entity_type=AuditEntityType.STORE_ACCESS,
            entity_id=None,  # Não tem ID único, é uma relação
            changes={
                "new_user_id": new_user.id,
                "user_name": new_user.name,
                "user_email": new_user.email,
                "user_phone": new_user.phone,
                "store_id": store.id,
                "store_name": store.name,
                "role": user_data.role_machine_name
            },
            description=f"Novo usuário '{new_user.name}' criado e vinculado à loja '{store.name}' como '{user_data.role_machine_name}'"
        )

        db.commit()
        db.refresh(new_access)

    except Exception as e:
        db.rollback()
        audit.log_failed_action(
            action=AuditAction.GRANT_STORE_ACCESS,
            entity_type=AuditEntityType.STORE_ACCESS,
            error=f"Erro ao criar acesso: {str(e)}"
        )
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro ao criar o acesso à loja: {str(e)}"
        )

    return new_access


# ===================================================================
# 🔥 PONTO VITAL 5: CONCESSÃO/ATUALIZAÇÃO DE ACESSO À LOJA
# ===================================================================
@router.put(
    "/{store_id}/accesses",
    response_model=StoreAccess,
    summary="Convidar usuário existente ou atualizar role"
)
def grant_or_update_store_access(
        request: Request,  # ✅ ADICIONAR
        db: GetDBDep,
        store: GetStoreDep,
        access_data: GrantStoreAccessRequest,
        current_user: GetCurrentUserDep,
        audit: GetAuditLoggerDep,  # ✅ ADICIONAR AUDITORIA
):
    """Concede acesso à loja para um usuário existente ou atualiza sua função."""

    if current_user.email.lower() == access_data.user_email.lower():
        audit.log_failed_action(
            action=AuditAction.UPDATE_USER_ROLE,
            entity_type=AuditEntityType.STORE_ACCESS,
            error="Tentativa de alterar própria função"
        )
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Você não pode alterar sua própria função na loja."
        )

    role = db.query(models.Role).filter(
        models.Role.machine_name == access_data.role_machine_name
    ).first()

    if not role:
        audit.log_failed_action(
            action=AuditAction.UPDATE_USER_ROLE,
            entity_type=AuditEntityType.STORE_ACCESS,
            error=f"Função não encontrada: {access_data.role_machine_name}"
        )
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"A função '{access_data.role_machine_name}' não foi encontrada."
        )

    if access_data.role_machine_name == 'owner':
        audit.log_failed_action(
            action=AuditAction.UPDATE_USER_ROLE,
            entity_type=AuditEntityType.STORE_ACCESS,
            error="Tentativa de atribuir função owner"
        )
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Não é permitido atribuir a função 'owner' via esta rota."
        )

    target_user = db.query(models.User).filter(
        func.lower(models.User.email) == access_data.user_email.lower()
    ).first()

    if not target_user:
        audit.log_failed_action(
            action=AuditAction.GRANT_STORE_ACCESS,
            entity_type=AuditEntityType.STORE_ACCESS,
            error=f"Usuário não encontrado: {access_data.user_email}"
        )
        db.commit()
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
            audit.log_failed_action(
                action=AuditAction.UPDATE_USER_ROLE,
                entity_type=AuditEntityType.STORE_ACCESS,
                error="Tentativa de alterar função de owner"
            )
            db.commit()
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Não é permitido alterar a função de um proprietário."
            )

        old_role = existing_access.role.machine_name
        existing_access.role = role

        # ✅ LOG DE ATUALIZAÇÃO DE FUNÇÃO
        audit.log(
            action=AuditAction.UPDATE_USER_ROLE,
            entity_type=AuditEntityType.STORE_ACCESS,
            entity_id=None,
            changes={
                "user_id": target_user.id,
                "user_name": target_user.name,
                "user_email": target_user.email,
                "store_id": store.id,
                "store_name": store.name,
                "old_role": old_role,
                "new_role": access_data.role_machine_name
            },
            description=f"Função de '{target_user.name}' alterada de '{old_role}' para '{access_data.role_machine_name}' na loja '{store.name}'"
        )

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

        # ✅ LOG DE NOVO ACESSO CONCEDIDO
        audit.log(
            action=AuditAction.GRANT_STORE_ACCESS,
            entity_type=AuditEntityType.STORE_ACCESS,
            entity_id=None,
            changes={
                "user_id": target_user.id,
                "user_name": target_user.name,
                "user_email": target_user.email,
                "store_id": store.id,
                "store_name": store.name,
                "role": access_data.role_machine_name
            },
            description=f"Usuário '{target_user.name}' adicionado à loja '{store.name}' como '{access_data.role_machine_name}'"
        )

        db.commit()
        db.refresh(new_access)

        return new_access


# ===================================================================
# 🔥 PONTO VITAL 6: REMOÇÃO DE ACESSO À LOJA
# ===================================================================
@router.delete("/{store_id}/accesses")
def delete_store_access(
        request: Request,  # ✅ ADICIONAR
        db: GetDBDep,
        store: GetStoreDep,
        user_id: int,
        user: GetCurrentUserDep,
        audit: GetAuditLoggerDep,  # ✅ ADICIONAR AUDITORIA
):
    """Remove o acesso de um usuário à loja."""
    if user.id == user_id:
        audit.log_failed_action(
            action=AuditAction.REVOKE_STORE_ACCESS,
            entity_type=AuditEntityType.STORE_ACCESS,
            error="Tentativa de remover próprio acesso"
        )
        db.commit()
        raise HTTPException(
            status_code=400,
            detail="Você não pode remover seu próprio acesso."
        )

    store_access = db.query(models.StoreAccess).filter(
        models.StoreAccess.store_id == store.id,
        models.StoreAccess.user_id == user_id
    ).first()

    if store_access is None:
        audit.log_failed_action(
            action=AuditAction.REVOKE_STORE_ACCESS,
            entity_type=AuditEntityType.STORE_ACCESS,
            error=f"Acesso não encontrado para user_id {user_id}"
        )
        db.commit()
        raise HTTPException(
            status_code=400,
            detail="Acesso não encontrado."
        )

    removed_user = store_access.user

    # ✅ LOG DE REMOÇÃO DE ACESSO
    audit.log(
        action=AuditAction.REVOKE_STORE_ACCESS,
        entity_type=AuditEntityType.STORE_ACCESS,
        entity_id=None,
        changes={
            "removed_user_id": removed_user.id,
            "removed_user_name": removed_user.name,
            "removed_user_email": removed_user.email,
            "store_id": store.id,
            "store_name": store.name,
            "role": store_access.role.machine_name
        },
        description=f"Acesso de '{removed_user.name}' removido da loja '{store.name}'"
    )

    db.delete(store_access)
    db.commit()


# ===================================================================
# ROTAS SEM AUDITORIA (NÃO SÃO CRÍTICAS)
# ===================================================================
@router.get("", response_model=list[StoreWithRole])
def list_stores(db: GetDBDep, user: GetCurrentUserDep):
    """Retorna todas as lojas acessíveis pelo usuário."""
    db_store_accesses = db.query(models.StoreAccess).filter(
        models.StoreAccess.user == user
    ).all()

    result = []

    for access in db_store_accesses:
        store_dict = SubscriptionService.get_store_dict_with_subscription(
            store=access.store,
            db=db
        )

        access_dict = {
            'store': store_dict,
            'role': access.role,
            'store_id': access.store_id,
            'user_id': access.user_id,
        }

        result.append(StoreWithRole.model_validate(access_dict))

    return result


@router.get("/{store_id}", response_model=StoreDetails)
def get_store(store: Annotated[Store, Depends(GetStore([Roles.OWNER]))]):
    """Retorna os detalhes completos de uma loja."""
    return store


@router.get("/{store_id}/accesses", response_model=list[StoreAccess])
def get_store_accesses(db: GetDBDep, store: GetStoreDep):
    """Lista todos os usuários com acesso à loja."""
    store_accesses = db.query(models.StoreAccess).filter(
        models.StoreAccess.store_id == store.id
    ).all()
    return store_accesses


@router.get("/check-url/{url_slug}")
def check_url_availability(
        url_slug: str,
        db: GetDBDep,
        current_user: GetCurrentUserDep
):
    """Verifica disponibilidade de URL (requer autenticação)."""

    existing_store = db.query(models.Store).filter(
        func.lower(models.Store.url_slug) == url_slug.lower()
    ).first()

    if existing_store:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Esta URL já está em uso por outra loja."
        )

    return Response(status_code=status.HTTP_204_NO_CONTENT)