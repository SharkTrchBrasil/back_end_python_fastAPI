# src/api/admin/routes/store.py
from typing import Annotated

from fastapi import APIRouter, HTTPException, Depends, Body, UploadFile
from fastapi.params import File
from sqlalchemy.orm import Session

from src.api.admin.schemas.store import StoreCreate, StoreWithRole, Roles, Store, StoreUpdate
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
    store_create: StoreCreate,
    image: UploadFile | None = File(None),
):
    logo_file_key = upload_file(image) if image else None

    # 1) cria a loja e grava no banco
    db_store = models.Store(
        name=store_create.name,
        phone=store_create.phone,
        language=store_create.language,
        country=store_create.country,
        currency=store_create.currency,
        is_active=store_create.is_active,
        zip_code=store_create.zip_code,
        street=store_create.street,
        number=store_create.number,
        neighborhood=store_create.neighborhood,
        complement=store_create.complement,
        reference=store_create.reference,
        city=store_create.city,
        state=store_create.state,
        logo_url=store_create.logo_url,  # Você pode manter este campo, se tiver outro uso
        instagram=store_create.instagram,
        facebook=store_create.facebook,
        plan_type=store_create.plan_type,
        logo_file_key=logo_file_key  # Adicione o file_key do logo AQUI
    )


    db.add(db_store)
    db.flush()                     # ← gera db_store.id sem dar commit

    # 2) vincula o usuário dono (código existente)
    db_role = (
        db.query(models.Role)
        .filter(models.Role.machine_name == "owner")
        .first()
    )
    db_store_access = models.StoreAccess(
        user=user,
        role=db_role,
        store=db_store,
    )
    db.add(db_store_access)

    # 3) meios de pagamento default (código existente)
    defaults = [...]
    for data in defaults:
        db.add(models.StorePaymentMethod(store_id=db_store.id, **data))

    # 4) salva tudo de uma vez
    db.commit()
    db.refresh(db_store_access)     # garante dados atualizados no retorno
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

# alterado do original pelo gpt
@router.patch("/{store_id}", response_model=Store)
def patch_store(
    db: GetDBDep,
    store: Annotated[Store, Depends(GetStore([Roles.OWNER]))],
    store_update: StoreUpdate,
    image: UploadFile | None = File(None),  # Adicione o parâmetro para receber a imagem
):
    file_key_to_delete = None

    if image:
        # Se uma nova imagem foi enviada:
        new_file_key = upload_file(image)
        if store.logo_file_key:
            file_key_to_delete = store.logo_file_key
        store.logo_file_key = new_file_key

    # Atualiza os outros campos da loja
    for field, value in store_update.model_dump(exclude_unset=True).items():
        setattr(store, field, value)
    db.commit()

    # Deleta a imagem antiga, se existir
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
