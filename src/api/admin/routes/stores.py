# src/api/admin/routes/store.py
import asyncio
import uuid
from datetime import datetime, timedelta
from typing import Annotated

from fastapi import APIRouter, HTTPException, Depends, UploadFile, Form
from fastapi.params import File
from slugify import slugify
from sqlalchemy.orm import joinedload


from src.api.admin.schemas.store_access import StoreAccess
from src.api.app.events.socketio_emitters import emit_store_updated
from src.api.shared_schemas.store import StoreWithRole, StoreCreate, Store, Roles
from src.core import models
from src.core.aws import upload_file, delete_file
from src.core.database import GetDBDep
from src.core.defaults.delivery_methods import default_delivery_settings
from src.core.defaults.payment_methods import default_payment_methods
from src.core.dependencies import GetCurrentUserDep, GetStoreDep, GetStore
from src.core.utils.unique_slug import generate_unique_slug

router = APIRouter(prefix="/stores", tags=["Stores"])


@router.post("", response_model=StoreWithRole)
def create_store(
    db: GetDBDep,
    user: GetCurrentUserDep,
    store_create: StoreCreate
):





    db_store = models.Store(
        name=store_create.name,
        phone=store_create.phone,
        store_url=generate_unique_slug(db, store_create.name)
    )
    db.add(db_store)
    db.flush()  # agora sim



    # Cria as configurações de entrega usando o id já gerado
    db_delivery_settings = models.StoreDeliveryConfiguration(
        store_id=db_store.id,
        delivery_enabled=default_delivery_settings["delivery_enabled"],
        delivery_estimated_min=default_delivery_settings["delivery_estimated_min"],
        delivery_estimated_max=default_delivery_settings["delivery_estimated_max"],
        delivery_fee=default_delivery_settings["delivery_fee"],
        delivery_min_order=default_delivery_settings["delivery_min_order"],

        pickup_enabled=default_delivery_settings["pickup_enabled"],
        pickup_estimated_min=default_delivery_settings["pickup_estimated_min"],
        pickup_estimated_max=default_delivery_settings["pickup_estimated_max"],
        pickup_instructions=default_delivery_settings["pickup_instructions"],

        table_enabled=default_delivery_settings["table_enabled"],
        table_estimated_min=default_delivery_settings["table_estimated_min"],
        table_estimated_max=default_delivery_settings["table_estimated_max"],
        table_instructions=default_delivery_settings["table_instructions"],
    )
    db.add(db_delivery_settings)

    # Cria as configurações gerais da loja (settings)
    db_store_settings = models.StoreSettings(
        store_id=db_store.id,
        is_delivery_active=True,
        is_takeout_active=True,
        is_table_service_active=True,
        is_store_open=True,
        auto_accept_orders=False,
        auto_print_orders=False
    )
    db.add(db_store_settings)




    totem_token = str(uuid.uuid4())


    totem_auth = models.TotemAuthorization(
        store_id=db_store.id,
        totem_token=totem_token,
        public_key = totem_token,
        totem_name = db_store.name,
        granted=True,
        granted_by_id= user.id,
        store_url=db_store.store_url,
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
    end_date = start_date + timedelta(days=365 * 100)

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


@router.get("/{store_id}", response_model=Store)
def get_store(
    store: Annotated[Store, Depends(GetStore([Roles.OWNER]))],
):
    return store





@router.patch("/{store_id}", response_model=Store)
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

):
    file_key_to_delete = None

    # Se uma nova logo for enviada, faça o upload e substitua
    if image:
        file_key_to_delete = store.file_key
        new_file_key = upload_file(image)
        store.file_key = new_file_key

    banner_key_to_delete = None

    if banner:
        banner_key_to_delete = store.banner_file_key
        new_banner_key = upload_file(banner)
        store.banner_file_key = new_banner_key


    if name is not None: store.name = name
    if phone is not None: store.phone = phone
    if email is not None: store.email = email
    if site is not None: store.site = site
    if instagram is not None: store.instagram = instagram
    if facebook is not None: store.facebook = facebook
    if tiktok is not None: store.tiktok = tiktok
    if whatsapp is not None: store.whatsapp = whatsapp
    if about is not None: store.about = about
    if cnpj is not None: store.cnpj = cnpj
    if description is not None: store.description = description

    # Endereço
    if zip_code is not None: store.zip_code = zip_code
    if street is not None: store.street = street
    if number is not None: store.number = number
    if neighborhood is not None: store.neighborhood = neighborhood
    if complement is not None: store.complement = complement
    if reference is not None: store.reference = reference
    if city is not None: store.city = city
    if state is not None: store.state = state

    # Confirmar as mudanças no banco de dados
    db.add(store)
    db.commit()
    db.refresh(store)

    if file_key_to_delete:
        delete_file(file_key_to_delete)

    if banner_key_to_delete:
        delete_file(banner_key_to_delete)


    await asyncio.create_task(emit_store_updated(store))

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





