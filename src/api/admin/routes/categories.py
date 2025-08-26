import asyncio
from decimal import Decimal

from fastapi import APIRouter, Form, HTTPException, File, UploadFile

from src.api.admin.socketio.emitters import admin_emit_store_updated
from src.api.app.socketio.socketio_emitters import emit_products_updated, emit_store_updated
from src.api.schemas.category import CategoryOut
from src.core import models
from src.core.aws import upload_file, delete_file
from src.core.database import GetDBDep
from src.core.dependencies import GetStoreDep
from src.core.utils.enums import CashbackType

router = APIRouter(tags=["Categories"], prefix="/stores/{store_id}/categories")


@router.post("", response_model=CategoryOut)
async def create_category(
        db: GetDBDep,
        store: GetStoreDep,
        name: str = Form(...),
        # ✅ REMOVIDO: 'priority' não é mais um parâmetro do formulário.
        # priority: int = Form(...),
        image: UploadFile = File(...),
        is_active: bool = Form(True),
        cashback_type: str = Form(default=CashbackType.NONE.value),
        cashback_value: Decimal = Form(default=Decimal('0.00')),
):
    # ✅ LÓGICA DE PRIORIDADE AUTOMÁTICA
    # 1. Conta quantas categorias já existem nesta loja.
    current_category_count = db.query(models.Category).filter(
        models.Category.store_id == store.id
    ).count()

    # 2. A contagem atual será a prioridade da nova categoria (ex: se já existem 3, a nova será a 4ª com prioridade 3).
    new_priority = current_category_count

    file_key = upload_file(image)

    db_category = models.Category(
        name=name,
        store_id=store.id,  # É uma boa prática passar o ID diretamente
        priority=new_priority,  # ✅ USA a prioridade calculada
        file_key=file_key,
        is_active=is_active,
        cashback_type=CashbackType(cashback_type),
        cashback_value=cashback_value
    )

    db.add(db_category)
    db.commit()
    db.refresh(db_category)

    # Não é necessário emitir o evento duas vezes, o admin_emit já cobre o caso.
    # await asyncio.create_task(emit_store_updated(db, store.id))
    await admin_emit_store_updated(db, store.id)

    return db_category

@router.get("", response_model=list[CategoryOut])
def get_categories(
    db: GetDBDep,
    store: GetStoreDep,
):
    db_categories = db.query(models.Category).filter(models.Category.store_id == store.id).all()
    return db_categories


@router.get("/{category_id}", response_model=CategoryOut)
def get_category(
    db: GetDBDep,
    store: GetStoreDep,
    category_id: int,
):
    db_category = db.query(models.Category).filter(
        models.Category.id == category_id,
        models.Category.store_id == store.id
    ).first()

    if not db_category:
        raise HTTPException(status_code=404, detail="Category not found")

    return db_category


@router.patch("/{category_id}", response_model=CategoryOut)
async def patch_category(
    db: GetDBDep,
    store: GetStoreDep,
    category_id: int,
    name: str | None = Form(None),
    priority: int | None = Form(None),
    image: UploadFile | None = File(None),
    is_active: bool | None = Form(None),  # Corrigido de Form(True) para Form(None)

    # ✅ ADICIONADO: Campos de cashback opcionais para atualização
    cashback_type: str | None = Form(None),
    cashback_value: Decimal | None = Form(None),
):
    db_category = db.query(models.Category).filter(
        models.Category.id == category_id,
        models.Category.store_id == store.id
    ).first()

    if not db_category:
        raise HTTPException(status_code=404, detail="Category not found")

    file_key_to_delete = None

    if name is not None:
        db_category.name = name
    if is_active is not None:
        db_category.is_active = is_active
    if priority is not None:
        db_category.priority = priority

    # ✅ Atualizar os campos de cashback
    if cashback_type is not None:
        db_category.cashback_type = CashbackType(cashback_type)
    if cashback_value is not None:
        db_category.cashback_value = cashback_value

    if image:
        file_key_to_delete = db_category.file_key
        new_file_key = upload_file(image)
        db_category.file_key = new_file_key

    db.commit()
    db.refresh(db_category)

    if file_key_to_delete:
        delete_file(file_key_to_delete)

    await asyncio.create_task(emit_store_updated(db, store.id))
    await admin_emit_store_updated(db, store.id)

    return db_category


@router.delete("/{category_id}", status_code=204)
async def delete_category(
    category_id: int,
    db: GetDBDep,
    store: GetStoreDep,
):
    category = db.query(models.Category).filter(
        models.Category.id == category_id,
        models.Category.store_id == store.id
    ).first()

    if not category:
        raise HTTPException(status_code=404, detail="Category not found")

    # Deletar os arquivos dos produtos da categoria
    for product in category.products:
        if product.file_key:
            delete_file(product.file_key)

    db.delete(category)
    db.commit()
    db.refresh(store)

    await asyncio.create_task(emit_store_updated(db, store.id))
    await admin_emit_store_updated(db, store.id)
