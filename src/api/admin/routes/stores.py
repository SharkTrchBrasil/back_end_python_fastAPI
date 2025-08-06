# src/api/admin/routes/store.py
import asyncio
import uuid
from datetime import datetime, timedelta
from typing import Annotated

from fastapi import  UploadFile, Form
from fastapi.params import File

from sqlalchemy import func


from src.api.admin.schemas.store_access import StoreAccess
from src.api.admin.socketio.emitters import admin_emit_store_updated
from src.api.app.events.socketio_emitters import emit_store_updated
from src.api.shared_schemas.store import StoreWithRole, StoreCreate, Store, Roles
from src.api.shared_schemas.store_details import StoreDetails
from src.core import models

from src.core.aws import upload_file, delete_file
from src.core.database import GetDBDep
from src.core.defaults.delivery_methods import default_delivery_settings

from src.core.dependencies import GetCurrentUserDep, GetStoreDep, GetStore
from src.core.models import StoreVerificationStatus
from src.core.utils.unique_slug import generate_unique_slug
from fastapi import APIRouter, Depends, HTTPException, status, Response
router = APIRouter(prefix="/stores", tags=["Stores"])


@router.post("", response_model=StoreWithRole)
def create_store(
        db: GetDBDep,
        user: GetCurrentUserDep,
        store_data: StoreCreate
):
    # Criação da loja com todos os campos
    db_store = models.Store(
        name=store_data.name,
        phone=store_data.phone,
        url_slug=store_data.store_url,
        description=store_data.description,
        segment_id=store_data.segment_id,
        cnpj=store_data.cnpj,

        # Dados de endereço
        zip_code=store_data.address.cep,
        street=store_data.address.street,
        number=store_data.address.number,
        complement=store_data.address.complement,
        neighborhood=store_data.address.neighborhood,
        city=store_data.address.city,
        state=store_data.address.uf,

        # Dados do responsável
        responsible_name=store_data.responsible.name,
        responsible_phone=store_data.responsible.phone,

        # Valores padrão
        is_active=True,
        is_setup_complete=False,
        verification_status=StoreVerificationStatus.UNVERIFIED
    )


    db.add(db_store)
    db.flush()



    # Cria as configurações de entrega usando o id já gerado
    # Cria a configuração unificada da loja usando o id já gerado
    db_store_configuration = models.StoreOperationConfig(
        store_id=db_store.id,

        # --- Campos que eram do 'StoreSettings' ---
        is_store_open=True,
        auto_accept_orders=False,
        auto_print_orders=False,
        # (os campos de impressora podem ficar com o valor padrão do banco de dados, que é None)

        # --- Campos que eram do 'StoreDeliveryConfiguration' ---
        # Usamos .get() para pegar os valores do seu dicionário de defaults de forma segura
        delivery_enabled=default_delivery_settings.get("delivery_enabled", True),
        delivery_estimated_min=default_delivery_settings.get("delivery_estimated_min"),
        delivery_estimated_max=default_delivery_settings.get("delivery_estimated_max"),
        delivery_fee=default_delivery_settings.get("delivery_fee"),
        delivery_min_order=default_delivery_settings.get("delivery_min_order"),

        pickup_enabled=default_delivery_settings.get("pickup_enabled", True),
        pickup_estimated_min=default_delivery_settings.get("pickup_estimated_min"),
        pickup_estimated_max=default_delivery_settings.get("pickup_estimated_max"),
        pickup_instructions=default_delivery_settings.get("pickup_instructions"),

        table_enabled=default_delivery_settings.get("table_enabled", True),
        table_estimated_min=default_delivery_settings.get("table_estimated_min"),
        table_estimated_max=default_delivery_settings.get("table_estimated_max"),
        table_instructions=default_delivery_settings.get("table_instructions"),
    )

    # Adiciona o único objeto de configuração ao banco de dados
    db.add(db_store_configuration)

    totem_token = str(uuid.uuid4())

    totem_auth = models.TotemAuthorization(
        store_id=db_store.id,
        totem_token=totem_token,
        public_key = totem_token,
        totem_name = db_store.name,
        granted=True,
        granted_by_id= user.id,
        store_url=db_store.url_slug,
    )
    db.add(totem_auth)

    # Cria vínculo do usuário com a loja como dono
    db_role = db.query(models.Role).filter(models.Role.machine_name == "owner").first()
    db_store_access = models.StoreAccess(user=user, role=db_role, store=db_store)
    db.add(db_store_access)

    # Busca pelo plano gratuito ("Essencial") no banco de dados
    free_plan = db.query(models.Plans).filter_by(price=0, available=True).first()

    # Validação crítica: Garante que um plano gratuito exista no sistema.
    # Sem ele, o modelo de negócio não funciona.
    if not free_plan:
        db.rollback()  # Desfaz a criação da loja para manter a consistência dos dados
        raise HTTPException(
            status_code=500,  # Erro interno do servidor
            detail="Erro de configuração do sistema: Nenhum plano gratuito foi encontrado."
        )

    # Define o período da assinatura gratuita como "infinita" (ex: 100 anos)
    start_date = datetime.utcnow()
    end_date = start_date + timedelta(days=365)

    # Cria a assinatura inicial para a nova loja, já no plano gratuito
    store_subscription = models.StoreSubscription(
        store=db_store,  # 'db_store' é a loja que acabou de ser criada no passo anterior
        plan=free_plan,
        status="active",
        current_period_start=start_date,
        current_period_end=end_date,
        gateway_subscription_id=None  # Plano gratuito não tem ID de gateway
    )
    db.add(store_subscription)

    # Comita a criação da loja e da sua assinatura inicial juntas
    db.commit()
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
        store.file_key = upload_file(image)

    banner_key_to_delete = None
    if banner:
        banner_key_to_delete = store.banner_file_key
        store.banner_file_key = upload_file(banner)

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
    await admin_emit_store_updated(store)
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