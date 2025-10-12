# src/api/admin/routes/store.py
import asyncio
import base64
import uuid
from datetime import datetime, timedelta, timezone
from typing import Annotated

from fastapi import  UploadFile, Form
from fastapi.params import File

from sqlalchemy import func

from src.api.admin.services.cloning_service import clone_store_data
from src.api.schemas.auth.store_access import StoreAccess
from src.api.admin.socketio.emitters import admin_emit_store_updated, admin_emit_stores_list_update
from src.core.utils.enums import StoreVerificationStatus, Roles
from src.api.app.socketio.socketio_emitters import emit_store_updated
from src.api.schemas.store.store import Store
from src.api.schemas.store.store_with_role import StoreWithRole
from src.api.schemas.store.store_details import StoreDetails
from src.core import models

from src.core.aws import delete_file, upload_single_file
from src.core.database import GetDBDep
from src.core.defaults.delivery_methods import default_delivery_settings

from src.core.dependencies import GetCurrentUserDep, GetStoreDep, GetStore

from fastapi import APIRouter, Depends, HTTPException, status, Response
router = APIRouter(prefix="/stores", tags=["Stores"])


# ✅ ROTA CORRIGIDA E FINALIZADA
@router.post("", response_model=StoreWithRole)
async def create_store(
        db: GetDBDep,
        user: GetCurrentUserDep,
        # --- Dados via Formulário (como no PATCH) ---
        name: str = Form(...),
        store_url: str = Form(...),
        phone: str = Form(...),
        description: str | None = Form(None),
        cnpj: str | None = Form(None),
        segment_id: int = Form(...),
        # Endereço
        cep: str = Form(...),
        street: str = Form(...),
        number: str = Form(...),
        complement: str | None = Form(None),
        neighborhood: str = Form(...),
        city: str = Form(...),
        uf: str = Form(...),
        # Responsável
        responsible_name: str = Form(...),
        responsible_phone: str = Form(...),

):
    # =======================================================================
    # ✅ PASSO 1: VALIDAÇÕES DE UNICIDADE
    # =======================================================================
    print("🔎 Verificando se os dados já existem no banco...")

    # 1. Verifica se o CNPJ da loja já está em uso (se foi fornecido)
    if cnpj:
        existing_store_by_cnpj = db.query(models.Store).filter(models.Store.cnpj == cnpj).first()
        if existing_store_by_cnpj:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="O CNPJ informado já está cadastrado em outra loja."
            )

    # 3. Verifica se o telefone do responsável já está em uso por OUTRO usuário
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

    print("👍 Dados únicos. Prosseguindo com a criação da loja...")

    # =======================================================================



    # =======================================================================
    # PASSO 3: CRIA A LOJA
    # =======================================================================
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

    # =======================================================================
    # ✅ NOVO BLOCO: CRIAÇÃO DO SALÃO E MESAS PADRÃO
    # =======================================================================
    print(f"Criando salão e mesas padrão para a loja ID: {db_store.id}...")

    # 1. Cria o Salão Principal
    default_saloon = models.Saloon(
        store_id=db_store.id,
        name="Salão Principal"
    )
    db.add(default_saloon)
    db.flush()  # Para obter o ID do salão para as mesas

    # 2. Cria 10 mesas padrão dentro do salão
    default_tables = []
    for i in range(1, 11):
        table = models.Tables(
            store_id=db_store.id,
            saloon_id=default_saloon.id,
            name=f"Mesa {i:02d}",  # Formata como "Mesa 01", "Mesa 02", etc.
            max_capacity=4  # Capacidade padrão
        )
        default_tables.append(table)

    db.add_all(default_tables)
    print("✅ Salão e mesas padrão criados com sucesso.")
    # =======================================================================




    # =======================================================================
    # ✅ NOVO BLOCO: POPULA AS CONFIGURAÇÕES DO CHATBOT PARA A NOVA LOJA
    # =======================================================================
    print(f"Populating default chatbot messages for new store ID: {db_store.id}...")

    # 1. Busca todos os templates mestres que acabamos de semear
    all_templates = db.query(models.ChatbotMessageTemplate).all()

    # 2. Cria uma configuração padrão para cada template, vinculada à nova loja
    for template in all_templates:
        # A mensagem de fidelidade começa desativada por padrão
        is_active_default = template.message_key != 'loyalty_program'

        new_store_message_config = models.StoreChatbotMessage(
            store_id=db_store.id,
            template_key=template.message_key,
            is_active=is_active_default
            # custom_content fica nulo, então o sistema usará o padrão do template
        )
        db.add(new_store_message_config)

    print("✅ Default chatbot messages created.")
    # =======================================================================

    # ✅ NOVO BLOCO: POPULA AS FORMAS DE PAGAMENTO PADRÃO
    print(f"Populating default payment methods for new store ID: {db_store.id}...")

    # 1. Busca todos os métodos de pagamento da plataforma marcados como padrão
    default_payment_methods = db.query(models.PlatformPaymentMethod).filter(
        models.PlatformPaymentMethod.is_default_for_new_stores == True
    ).all()

    # 2. Cria uma entrada na tabela de ativação para cada método padrão
    new_store_payment_activations = []
    for platform_method in default_payment_methods:
        new_store_payment_activations.append(
            # Usa o seu modelo existente: StorePaymentMethodActivation
            models.StorePaymentMethodActivation(
                store_id=db_store.id,
                platform_payment_method_id=platform_method.id,
                is_active=True  # Já começa ativo por padrão
            )
        )

    if new_store_payment_activations:
        db.add_all(new_store_payment_activations)

    print("✅ Default payment methods created.")
    # =======================================================================


    # =======================================================================
    # PASSO 5: CRIA OBJETOS RELACIONADOS (Sua lógica está perfeita)
    # =======================================================================

    # O Python automaticamente vai mapear as chaves do dicionário para os parâmetros do modelo.
    db_store_configuration = models.StoreOperationConfig(
        store_id=db_store.id,
        is_store_open=True,
        auto_accept_orders=False,
        auto_print_orders=False,
        **default_delivery_settings  # <--- A mágica acontece aqui
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

    # =======================================================================
    # ✅ CRIAÇÃO DA ASSINATURA COM TRIAL DE 30 DIAS
    # =======================================================================

    # 1. Busca o plano principal da sua plataforma (Ex: "Plano Pro")
    # Em vez de procurar um plano com preço 0, buscamos o plano que será usado.
    main_plan = db.query(models.Plans).first()

    if not main_plan:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail="Configuração do sistema: Nenhum plano principal foi encontrado."
        )

    # 2. Define as datas de início e fim do trial
    start_date = datetime.now(timezone.utc)
    # O trial termina exatamente 30 dias a partir de agora
    end_date = start_date + timedelta(days=30)

    # 3. Cria a assinatura com o status 'trialing'
    store_subscription = models.StoreSubscription(
        store=db_store,
        plan=main_plan,
        status="trialing",  # <-- MUDANÇA IMPORTANTE: O status inicial é 'trialing'
        current_period_start=start_date,
        current_period_end=end_date,  # <-- Fim do período de teste
    )
    db.add(store_subscription)

    # =======================================================================
    # PASSO FINAL: COMMIT E RETORNO (sem alterações)
    # =======================================================================
    db.commit()
    db.refresh(db_store_access)

    # Primeiro, atualiza a lista "magra" de lojas para todos os painéis do admin
    await admin_emit_stores_list_update(db, admin_user=user)


    await admin_emit_store_updated(db, store_id=db_store.id)

    # O retorno para a chamada HTTP continua o mesmo
    return db_store_access

# ✅ ENDPOINT DE CLONAGEM ATUALIZADO
@router.post("/clone", response_model=StoreWithRole, status_code=status.HTTP_201_CREATED)
async def clone_store(
        db: GetDBDep,
        user: GetCurrentUserDep,
        source_store_id: int = Form(...),
        name: str = Form(...),
        url_slug: str = Form(...),
        phone: str = Form(...),
        description: str | None = Form(None),
        # Endereço como JSON
        address_json: str = Form(..., alias="address"),
        # Opções de clonagem como JSON
        options_json: str = Form(..., alias="options"),
):
    """
    Cria uma nova loja clonando dados de uma loja de origem.
    """
    import json
    address = json.loads(address_json)
    options = json.loads(options_json)

    # 1. Valida se a loja de origem existe e se o usuário tem acesso a ela
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

    # 2. Validações de unicidade para a nova loja (URL, etc.)
    existing_by_url = db.query(models.Store).filter(models.Store.url_slug == url_slug).first()
    if existing_by_url:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A URL informada já está em uso."
        )

    # 3. Cria a nova loja base (sem os dados clonados ainda)
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

    # ✅ 4. CRIA CONFIGURAÇÕES PADRÃO ANTES DE CLONAR
    # Se a clonagem de 'operation_config' não for selecionada, criamos uma padrão.
    if not options.get('operation_config', False):
        db_store_configuration = models.StoreOperationConfig(
            store_id=new_store.id,
            is_store_open=True,
            **default_delivery_settings
        )
        db.add(db_store_configuration)

    # 5. Chama o serviço de clonagem para popular os dados
    clone_store_data(db, source_store_id=source_store.id, new_store_id=new_store.id, options=options)

    # 6. Cria o acesso de 'owner' para o usuário na nova loja
    owner_role = db.query(models.Role).filter(models.Role.machine_name == "owner").first()
    new_access = models.StoreAccess(user=user, role=owner_role, store=new_store)
    db.add(new_access)

    # 7. Cria a assinatura com trial
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

    # Emite eventos, etc.
    await admin_emit_stores_list_update(db, admin_user=user)
    await admin_emit_store_updated(db, store_id=new_store.id)

    return new_access



@router.get("", response_model=list[StoreWithRole])  # ✅ Agora tipado
def list_stores(
    db: GetDBDep,
    user: GetCurrentUserDep,
):
    """
    Retorna a lista de lojas acessíveis pelo usuário, com subscription calculada.
    """
    db_store_accesses = db.query(models.StoreAccess).filter(
        models.StoreAccess.user == user
    ).all()

    # ✅ Conversão automática via Pydantic (mais limpo!)
    return [
        StoreWithRole.model_validate(access)
        for access in db_store_accesses
    ]



@router.get("/{store_id}", response_model=StoreDetails)
def get_store(
    store: Annotated[Store, Depends(GetStore([Roles.OWNER]))],
):
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
    description:  str | None = Form(None),
    image: UploadFile | None = File(None),
    banner: UploadFile | None = File(None),
    # --- ✅ Novos campos do Wizard ---
    url_slug: str | None = Form(None),
    segment_id: int | None = Form(None),
    # Responsável
    responsible_name: str | None = Form(None),
    responsible_phone: str | None = Form(None),

    # Flag para saber se o wizard foi concluído
    is_setup_complete: bool | None = Form(None),

):
    # Lógica de upload de arquivos (já estava correta)
    file_key_to_delete = None
    if image:
        file_key_to_delete = store.file_key
        store.file_key = upload_single_file(image)

    banner_key_to_delete = None
    if banner:
        banner_key_to_delete = store.banner_file_key
        store.banner_file_key = upload_single_file(banner)

    # Dicionário com todos os campos para atualizar
    update_data = {
        "name": name, "phone": phone, "description": description,
        "url_slug": url_slug, "cnpj": cnpj, "segment_id": segment_id,
        "zip_code": zip_code, "street": street, "number": number,
        "neighborhood": neighborhood, "complement": complement, "city": city, "state": state,
        "responsible_name": responsible_name, "responsible_phone": responsible_phone,
        "is_setup_complete": is_setup_complete,
    }

    # Itera e atualiza apenas os campos que foram enviados
    for key, value in update_data.items():
        if value is not None:
            setattr(store, key, value)

    db.add(store)
    db.commit()
    db.refresh(store)

    # Lógica para deletar arquivos antigos (já estava correta)
    if file_key_to_delete:
        delete_file(file_key_to_delete)
    if banner_key_to_delete:
        delete_file(banner_key_to_delete)

    await asyncio.create_task(emit_store_updated(db,store.id))
    await admin_emit_store_updated(db, store.id)
    return store




@router.get("/{store_id}/accesses", response_model=list[StoreAccess])
def get_store_accesses(
    db: GetDBDep,
    store: GetStoreDep,
):
    store_accesses = db.query(models.StoreAccess).filter(models.StoreAccess.store_id == store.id).all()
    return store_accesses


@router.put("/{store_id}/accesses")
def create_or_update_store_access(
    db: GetDBDep,
    store: GetStoreDep,
    user_email: str,
    role: str,
    user: GetCurrentUserDep,
):
    if user.email == user_email:
        raise HTTPException(status_code=400, detail="Cannot update your own access")

    role = db.query(models.Role).filter(models.Role.machine_name == role).first()
    if role is None:
        raise HTTPException(status_code=404, detail="Role not found")

    user = db.query(models.User).filter(models.User.email == user_email).first()
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")

    store_access = db.query(models.StoreAccess).filter(
        models.StoreAccess.store_id == store.id,
        models.StoreAccess.user_id == user.id
    ).first()

    if store_access is None:
        store_access = models.StoreAccess(store=store, user=user, role=role)
        db.add(store_access)
    else:
        store_access.role = role

    db.commit()


@router.delete("/{store_id}/accesses")
def delete_store_access(
    db: GetDBDep,
    store: GetStoreDep,
    user_id: int,
    user: GetCurrentUserDep,
):
    if user.id == user_id:
        raise HTTPException(status_code=400, detail="Cannot delete your own access")
    store_access = db.query(models.StoreAccess).filter(
        models.StoreAccess.store_id == store.id,
        models.StoreAccess.user_id == user_id
    ).first()
    if store_access is None:
        raise HTTPException(status_code=400, detail="Invalid user_id")
    db.delete(store_access)
    db.commit()






@router.get(
    "/check-url/{url_slug}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Verificar a disponibilidade de uma URL para a loja"
)
def check_url_availability(url_slug: str,  db: GetDBDep):

    existing_store = db.query(models.Store).filter(
        func.lower(models.Store.url_slug) == url_slug.lower()
    ).first()

    # Se encontrou uma loja, significa que a URL já está em uso.
    if existing_store:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Esta URL já está em uso por outra loja."
        )

    # Se não encontrou nenhuma loja, a URL está livre.
    return Response(status_code=status.HTTP_204_NO_CONTENT)