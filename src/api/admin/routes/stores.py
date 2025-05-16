# src/api/admin/routes/store.py
from typing import Annotated

from fastapi import APIRouter, HTTPException, Depends, UploadFile, Form
from fastapi.params import File

from src.api.admin.schemas.store import StoreWithRole, Roles, Store, StoreCreate
from src.api.admin.schemas.store_access import StoreAccess
from src.core import models
from src.core.aws import upload_file, delete_file
from src.core.database import GetDBDep
from src.core.defaults.delivery_methods import default_delivery_settings
from src.core.defaults.payment_methods import default_payment_methods
from src.core.dependencies import GetCurrentUserDep, GetStoreDep, GetStore


router = APIRouter(prefix="/stores", tags=["Stores"])


@router.post("", response_model=StoreWithRole)
def create_store(
    db: GetDBDep,
    user: GetCurrentUserDep,
    store_create: StoreCreate
):
    # Cria a loja
    db_store = models.Store(name=store_create.name, phone=store_create.phone)
    db.add(db_store)
    db.flush()  # envia insert e gera db_store.id

    # Cria as formas de pagamento
    for payment in default_payment_methods:
        db_payment = models.StorePaymentMethods(
            store=db_store,
            payment_type=payment["payment_type"],
            custom_name=payment["custom_name"],
            custom_icon=payment.get("custom_icon"),
            change_back=payment.get("change_back", False),
            credit_in_account=False,
            is_active=True,
            active_on_delivery=True,
            active_on_pickup=True,
            active_on_counter=True,
            tax_rate=0.0,
            days_to_receive=0,
            has_fee=False,
            pix_key='',
            pix_key_active=payment.get("pix_key_active", False)
        )
        db.add(db_payment)

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

    # Cria vínculo do usuário com a loja como dono
    db_role = db.query(models.Role).filter(models.Role.machine_name == "owner").first()
    db_store_access = models.StoreAccess(user=user, role=db_role, store=db_store)
    db.add(db_store_access)

    # Comita tudo junto
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
def patch_store(
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
):
    file_key_to_delete = None

    # Se uma nova logo for enviada, faça o upload e substitua
    if image:
        file_key_to_delete = store.file_key
        new_file_key = upload_file(image)
        store.file_key = new_file_key

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

    # Se a logo foi alterada, exclua a antiga
    if file_key_to_delete:
        delete_file(file_key_to_delete)

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





