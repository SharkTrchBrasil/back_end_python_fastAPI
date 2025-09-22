# src/api/admin/routes/store.py
import asyncio
import base64
import uuid
from datetime import datetime, timedelta, timezone
from typing import Annotated

from fastapi import  UploadFile, Form
from fastapi.params import File

from sqlalchemy import func


from src.api.schemas.auth.store_access import StoreAccess
from src.api.admin.socketio.emitters import admin_emit_store_updated
from src.core.utils.enums import StoreVerificationStatus, Roles
from src.api.app.socketio.socketio_emitters import emit_store_updated
from src.api.schemas.store.store import StoreWithRole, Store
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
def create_store(
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
        # Assinatura
        signature_base64: str | None = Form(None)
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

    # =======================================================================
    # PASSO 4: PROCESSA A ASSINATURA (Sua lógica, um pouco ajustada)
    # =======================================================================
    if signature_base64:
        try:
            # Tenta remover o cabeçalho 'data:image/png;base64,' se ele existir
            if "," in signature_base64:
                header, encoded = signature_base64.split(",", 1)
            else:
                encoded = signature_base64

            image_data = base64.b64decode(encoded)

            # Supondo que você tenha a função 'upload_file_bytes'
            file_key = upload_single_file(image_data)
            db_store.signature_file_key = file_key
        except Exception as e:
            print(f"Erro ao processar a assinatura: {e}")
            raise HTTPException(status_code=400, detail="Formato de assinatura inválido.")

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

    free_plan = db.query(models.Plans).filter_by(price=0, available=True).first()
    if not free_plan:
        db.rollback()
        raise HTTPException(status_code=500, detail="Configuração do sistema: Nenhum plano gratuito encontrado.")

    start_date = datetime.now(timezone.utc)
    end_date = start_date + timedelta(days=365)
    store_subscription = models.StoreSubscription(
        store=db_store, plan=free_plan, status="active",
        current_period_start=start_date, current_period_end=end_date,
    )
    db.add(store_subscription)

    # =======================================================================
    # PASSO 6: COMMIT E RETORNO
    # =======================================================================
    db.commit()
    db.refresh(db_store_access)

    # Disparar o serviço de verificação aqui (como discutimos)
    # verification_service = VerificationService(db)
    # background_tasks.add_task(verification_service.start_verification_process, db_store, user)

    return db_store_access




@router.get("", response_model=list[StoreWithRole])
def list_stores(
    db: GetDBDep,
    user: GetCurrentUserDep,
):
    db_store_accesses = db.query(models.StoreAccess).filter(models.StoreAccess.user == user).all()
    return db_store_accesses

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