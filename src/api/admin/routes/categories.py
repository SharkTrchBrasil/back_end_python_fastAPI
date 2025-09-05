from fastapi import APIRouter, HTTPException

from src.api.admin.utils.emit_updates import emit_updates_products
from src.api.crud import crud_category, crud_option

from src.api.schemas.products.category import (
    CategoryCreate, Category, OptionGroup, OptionGroupCreate,
    OptionItemCreate, OptionItem, CategoryUpdate
)
from src.core.aws import delete_file
from src.core.database import GetDBDep
from src.core.dependencies import GetStoreDep

router = APIRouter(tags=["Categories"], prefix="/stores/{store_id}/categories")


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

    file_key_to_delete = db_category.file_key

    db.delete(db_category)
    db.commit()

    if file_key_to_delete:
        delete_file(file_key_to_delete)

    await emit_updates_products(db, store.id)




@router.post("/{category_id}/option-groups", response_model=OptionGroup, status_code=201)
async def create_option_group_route(category_id: int, group_data: OptionGroupCreate, db: GetDBDep, store: GetStoreDep):
    # Verifica se a categoria pertence à loja
    category = crud_category.get_category(db, category_id=category_id, store_id=store.id)
    if not category:
        raise HTTPException(status_code=404, detail="Category not found in this store")

    db_group = crud_option.create_option_group(db=db, group_data=group_data, category_id=category_id)
    await emit_updates_products(db, store.id)
    return db_group


@router.post("/option-groups/{group_id}/items", response_model=OptionItem, status_code=201)
async def create_option_item_route(group_id: int, item_data: OptionItemCreate, db: GetDBDep, store: GetStoreDep):
    # Verifica se o grupo pertence à loja (uma verificação de segurança extra)
    group = crud_option.get_option_group(db, group_id=group_id)
    if not group or group.category.store_id != store.id:
        raise HTTPException(status_code=404, detail="Option group not found in this store")

    db_item = crud_option.create_option_item(db=db, item_data=item_data, group_id=group_id)
    await emit_updates_products(db, store.id)
    return db_item