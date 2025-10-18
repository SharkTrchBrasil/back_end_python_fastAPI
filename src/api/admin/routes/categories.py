from fastapi import APIRouter, HTTPException, UploadFile, File

from src.api.admin.socketio.emitters import emit_updates_products
from src.api.crud import crud_category, crud_option
from src.api.schemas.products.category import (
    CategoryCreate, Category, OptionGroup, OptionGroupCreate,
    OptionItemCreate, OptionItem, CategoryUpdate
)
from src.core.aws import delete_file, upload_single_file
from src.core.database import GetDBDep
from src.core.dependencies import GetStoreDep

# Roteador principal com o prefixo da loja, para rotas que operam no nível da categoria
router = APIRouter(tags=["Categories"], prefix="/stores/{store_id}/categories")

# Roteador secundário SEM prefixo, para rotas que operam em recursos aninhados
nested_router = APIRouter(tags=["Categories Nested"])


# --- ROTAS NO ROTEADOR ANINHADO (nested_router) ---

@nested_router.post("/option-items/{item_id}/image", response_model=OptionItem, status_code=200)
async def upload_option_item_image(
    item_id: int,
    db: GetDBDep,
    image_file: UploadFile = File(...)
):
    # 1. Busca o item pelo ID
    db_item = crud_option.get_option_item(db, item_id=item_id)
    if not db_item:
        raise HTTPException(status_code=404, detail="Option Item not found")

    # 2. A partir do item, encontramos a loja para validação e para o caminho do S3
    store_id = db_item.group.category.store_id

    # 3. Se já houver uma imagem antiga, apaga ela do S3
    if db_item.file_key:
        delete_file(db_item.file_key)

    # 4. Faz o upload do novo arquivo
    folder_path = f"stores/{store_id}/option-items/{db_item.id}"
    file_key = upload_single_file(file=image_file, folder=folder_path)

    if not file_key:
        raise HTTPException(status_code=500, detail="Failed to upload image to S3")

    # 5. Atualiza o banco de dados com a nova file_key
    db_item.file_key = file_key
    db.commit()
    db.refresh(db_item)

    # 6. Emite a atualização e retorna o objeto completo
    await emit_updates_products(db, store_id)
    return db_item

@nested_router.post("/option-groups/{group_id}/items", response_model=OptionItem, status_code=201)
async def create_option_item_route(group_id: int, item_data: OptionItemCreate, db: GetDBDep):
    group = crud_option.get_option_group(db, group_id=group_id)
    if not group:
        raise HTTPException(status_code=404, detail="Option group not found")

    db_item = crud_option.create_option_item(db=db, item_data=item_data, group_id=group_id)
    await emit_updates_products(db, group.category.store_id)
    return db_item


# --- ROTAS NO ROTEADOR PRINCIPAL (router) ---

@router.post("", response_model=Category, status_code=201)
async def create_category(category_data: CategoryCreate, db: GetDBDep, store: GetStoreDep):
    db_category = crud_category.create_category(db=db, category_data=category_data, store_id=store.id)
    await emit_updates_products(db, store.id)
    return db_category

@router.get("", response_model=list[Category])
def get_categories(db: GetDBDep, store: GetStoreDep):
    return crud_category.get_all_categories(db, store_id=store.id)

@router.get("/{category_id}", response_model=Category)
def get_category(category_id: int, db: GetDBDep, store: GetStoreDep):
    db_category = crud_category.get_category(db, category_id=category_id, store_id=store.id)
    if not db_category:
        raise HTTPException(status_code=404, detail="Category not found")
    return db_category

@router.patch("/{category_id}", response_model=Category)
async def update_category(category_id: int, update_data: CategoryUpdate, db: GetDBDep, store: GetStoreDep):
    db_category = crud_category.get_category(db, category_id=category_id, store_id=store.id)
    if not db_category:
        raise HTTPException(status_code=404, detail="Category not found")

    updated_category = crud_category.update_category(db=db, db_category=db_category, update_data=update_data)
    await emit_updates_products(db, store.id)
    return updated_category

@router.delete("/{category_id}", status_code=204)
async def delete_category(category_id: int, db: GetDBDep, store: GetStoreDep):
    db_category = crud_category.get_category(db, category_id=category_id, store_id=store.id)
    if not db_category:
        raise HTTPException(status_code=404, detail="Category not found")

    if db_category.file_key:
        delete_file(db_category.file_key)

    db.delete(db_category)
    db.commit()
    await emit_updates_products(db, store.id)

@router.post("/{category_id}/option-groups", response_model=OptionGroup, status_code=201)
async def create_option_group_route(category_id: int, group_data: OptionGroupCreate, db: GetDBDep, store: GetStoreDep):
    category = crud_category.get_category(db, category_id=category_id, store_id=store.id)
    if not category:
        raise HTTPException(status_code=404, detail="Category not found in this store")

    db_group = crud_option.create_option_group(db=db, group_data=group_data, category_id=category_id)
    await emit_updates_products(db, store.id)
    return db_group