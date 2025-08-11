import asyncio
from decimal import Decimal

from fastapi import APIRouter, Form, HTTPException, File, UploadFile

from src.api.app.socketio.socketio_emitters import emit_products_updated
from src.api.schemas.category import CategoryOut
from src.core import models
from src.core.aws import upload_file, delete_file
from src.core.database import GetDBDep
from src.core.dependencies import GetStoreDep
from src.core.utils.enums import CashbackType

router = APIRouter(tags=["Categories"], prefix="/stores/{store_id}/categories")


@router.post("", response_model=CategoryOut) # Retorna o schema de saída
async def create_category(
    db: GetDBDep,
    store: GetStoreDep,
    name: str = Form(...),
    priority: int = Form(...),
    image: UploadFile = File(...),
    is_active: bool = Form(True),

    # ✅ ADICIONADO: Novos campos de cashback no formulário
    cashback_type: str = Form(default=CashbackType.NONE.value),
    cashback_value: Decimal = Form(default=Decimal('0.00')),
):
    file_key = upload_file(image)

    db_category = models.Category(
        name=name,
        store=store,
        priority=priority,
        file_key=file_key,
        is_active=is_active,
        # ✅ ADICIONADO: Passando os valores para o modelo do banco
        cashback_type=CashbackType(cashback_type),
        cashback_value=cashback_value
    )

    db.add(db_category)
    db.commit()
    await asyncio.create_task(emit_products_updated(db, store.id))

    # A resposta usará o schema `CategoryOut` e incluirá os novos campos
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
    db_category = db.query(models.Category).filter(models.Category.id == category_id, models.Category.store_id == store.id).first()
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
    # ✅ CORREÇÃO DE BUG: Sua lógica original para 'is_active' estava incorreta.
    if is_active is not None:
        db_category.is_active = is_active
    if priority is not None:
        db_category.priority = priority

    # ✅ ADICIONADO: Lógica para atualizar os campos de cashback
    if cashback_type is not None:
        db_category.cashback_type = CashbackType(cashback_type)
    if cashback_value is not None:
        db_category.cashback_value = cashback_value

    if image:
        file_key_to_delete = db_category.file_key
        new_file_key = upload_file(image)
        db_category.file_key = new_file_key

    db.commit()

    if file_key_to_delete:
        delete_file(file_key_to_delete)

    await asyncio.create_task(emit_products_updated(db, store.id))

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

    await asyncio.create_task(emit_products_updated(db, store.id))
