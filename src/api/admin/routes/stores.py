# src/api/admin/routes/store.py
from typing import Annotated, Optional

from fastapi import APIRouter, HTTPException, Depends, UploadFile, Form
from fastapi.params import File

from src.api.admin.schemas.store import StoreWithRole, Roles, Store, StoreCreate
from src.api.admin.schemas.store_access import StoreAccess
from src.core import models
from src.core.aws import upload_file, delete_file
from src.core.database import GetDBDep
from src.core.dependencies import GetCurrentUserDep, GetStoreDep, GetStore


router = APIRouter(prefix="/stores", tags=["Stores"])



@router.post("", response_model=StoreWithRole)
def create_store(
    db: GetDBDep,
    user: GetCurrentUserDep,
    store_create: StoreCreate
):
    db_store = models.Store(name=store_create.name)
    db_role = db.query(models.Role).filter(models.Role.machine_name == "owner").first()
    db_store_access = models.StoreAccess(user=user, role=db_role, store=db_store)
    db.add(db_store_access)
    db.commit()
    return db_store_access


# @router.post("", response_model=StoreWithRole)
# def create_store(
#     db: GetDBDep,
#     user: GetCurrentUserDep,
#     name: str = Form(...),
#
#     phone: str = Form(...),
#     is_active: bool = Form(...),
#     zip_code: str = Form(...),
#     street: str = Form(...),
#     number: str = Form(...),
#     neighborhood: str = Form(...),
#     complement: Optional[str] = Form(None),
#     reference: Optional[str] = Form(None),
#     city: str = Form(...),
#     state: str = Form(...),
#     instagram: Optional[str] = Form(None),
#     facebook: Optional[str] = Form(None),
#     tiktok: Optional[str] = Form(None),
#     plan_type: str = Form("free"),
#     image: Optional[UploadFile] = File(None),
# ):
#     if image:
#         file_key = upload_file(image)
#     else:
#         file_key = None
#
#     # 2) Criar a loja
#     db_store = models.Store(
#         name=name,
#
#         phone=phone,
#         is_active=is_active,
#         zip_code=zip_code,
#         street=street,
#         number=number,
#         neighborhood=neighborhood,
#         complement=complement,
#         reference=reference,
#         city=city,
#         state=state,
#         instagram=instagram,
#         facebook=facebook,
#         tiktok=tiktok,
#         plan_type=plan_type,
#         file_key=file_key
#     )
#
#     db.add(db_store)
#     db.flush()  # gera db_store.id sem dar commit
#
#     # 3) Vincular o usuário dono
#     db_role = db.query(models.Role).filter(models.Role.machine_name == "owner").first()
#     db_store_access = models.StoreAccess(
#         user=user,
#         role=db_role,
#         store=db_store,
#     )
#     db.add(db_store_access)
#
#     # 4) Adicionar métodos de pagamento (código existente)
#     defaults = [...]  # seu código aqui
#     for data in defaults:
#         db.add(models.StorePaymentMethod(store_id=db_store.id, **data))
#
#     # 5) Salvar tudo
#     db.commit()
#     db.refresh(db_store_access)
#
#     return db_store_access

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

# alterado do original pelo gpt
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
    address: str | None = Form(None),
    city: str | None = Form(None),
    state: str | None = Form(None),
    zipcode: str | None = Form(None),
    logo: UploadFile | None = File(None),
):
    file_key_to_delete = None

    # Se uma nova logo for enviada, faça o upload e substitua
    if logo:
        file_key_to_delete = store.logo_file_key
        new_file_key = upload_file(logo)
        store.logo_file_key = new_file_key


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
    if address is not None: store.address = address
    if city is not None: store.city = city
    if state is not None: store.state = state
    if zipcode is not None: store.zipcode = zipcode

    # Confirmar as mudanças no banco de dados
    db.commit()

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
