import asyncio
from decimal import Decimal

from fastapi import APIRouter, Form, HTTPException, File, UploadFile

from src.api import crud
from src.api.admin.socketio.emitters import admin_emit_store_updated, admin_emit_products_updated
from src.api.admin.utils.emit_updates import emit_updates_products
from src.api.app.socketio.socketio_emitters import emit_products_updated, emit_store_updated
from src.api.crud import crud_category, crud_option
from src.api.schemas.category import CategoryCreate, Category, OptionGroup, OptionGroupCreate, OptionItemCreate, \
    OptionItem, CategoryUpdate

from src.core import models
from src.core.aws import upload_file, delete_file
from src.core.database import GetDBDep
from src.core.dependencies import GetStoreDep
from src.core.utils.enums import CashbackType, CategoryType

router = APIRouter(tags=["Categories"], prefix="/stores/{store_id}/categories")


# --- ROTAS PARA CATEGORIAS ---

# ✨ 1. Alterado para async def e emitter adicionado
@router.post("", response_model=Category, status_code=201)
async def create_category_route(store_id: int, category_data: CategoryCreate,     db: GetDBDep,):
    # Primeiro, criamos a categoria no banco
    db_category = crud.crud_category.create_category(db=db, category_data=category_data, store_id=store_id)

    # ✨ Depois de salvar com sucesso, emitimos o evento
    await admin_emit_products_updated(db, store_id)

    # ✨ Por último, retornamos o resultado
    return db_category


@router.get("", response_model=list[Category])
def get_categories_route(store_id: int,     db: GetDBDep,):
    return crud.crud_category.get_all_categories(db, store_id=store_id)


@router.get("/{category_id}", response_model=Category)
def get_category_route(category_id: int, store_id: int,     db: GetDBDep,):
    db_category = crud.crud_category.get_category(db, category_id=category_id, store_id=store_id)
    if not db_category:
        raise HTTPException(status_code=404, detail="Category not found")
    return db_category


# --- ROTAS PARA GRUPOS DE OPÇÕES ---

# ✨ 2. Alterado para async def e emitter adicionado
@router.post("/{category_id}/option-groups", response_model=OptionGroup, status_code=201)
async def create_option_group_route(category_id: int, group_data: OptionGroupCreate,     db: GetDBDep,):
    # Precisamos saber o store_id para emitir o evento. Buscamos a categoria pai.
    category = crud.crud_category.get_category(db, category_id=category_id)
    if not category:
        raise HTTPException(status_code=404, detail="Category not found")

    db_group = crud.crud_option.create_option_group(db=db, group_data=group_data, category_id=category_id)

    # Emitimos o evento para a loja correta
    await emit_updates_products(db, category.store_id)

    return db_group


# --- ROTAS PARA ITENS DE OPÇÃO ---

# ✨ 3. Alterado para async def e emitter adicionado
@router.post("/option-groups/{group_id}/items", response_model=OptionItem, status_code=201)
async def create_option_item_route(group_id: int, item_data: OptionItemCreate,     db: GetDBDep,):
    # Lógica similar para encontrar o store_id através do grupo pai
    group = crud.crud_option.get_option_group(db, group_id=group_id)
    if not group:
        raise HTTPException(status_code=404, detail="Option group not found")

    db_item = crud.crud_option.create_option_item(db=db, item_data=item_data, group_id=group_id)

    await emit_updates_products(db, group.category.store_id)

    return db_item



@router.get("", response_model=list[Category])
def get_categories(
        db: GetDBDep,
        store: GetStoreDep,
):
    db_categories = db.query(models.Category).filter(models.Category.store_id == store.id).all()
    return db_categories


@router.get("/{category_id}", response_model=Category)
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

@router.patch("/{category_id}", response_model=Category)
async def patch_category(
    category_id: int,
    update_data: CategoryUpdate, # 👈 Recebe o schema Pydantic, não mais Form()
    db: GetDBDep,
    store: GetStoreDep,
):
    # A busca pelo objeto no banco continua a mesma
    db_category = db.query(models.Category).filter(
        models.Category.id == category_id,
        models.Category.store_id == store.id
    ).first()

    if not db_category:
        raise HTTPException(status_code=404, detail="Category not found")

    # Pega os dados do schema e os converte para um dicionário,
    # excluindo os campos que não foram enviados pelo cliente (mantendo os valores atuais).
    update_dict = update_data.model_dump(exclude_unset=True)

    # Itera sobre os campos enviados e atualiza o objeto do banco
    for key, value in update_dict.items():
        setattr(db_category, key, value)

    db.commit()
    db.refresh(db_category)

    # A lógica de emitir o evento continua a mesma
    await emit_updates_products(db, store.id)

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

    await emit_updates_products(db, store.id)
