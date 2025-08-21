# Em: src/api/routers/payable_category_router.py
from fastapi import APIRouter, HTTPException

from src.api.admin.services.payable_category_service import payable_category_service
from src.core.database import GetDBDep
from src.core.dependencies import GetStoreDep
from src.api.schemas.payable_category import (
    PayableCategoryCreate,
    PayableCategoryUpdate,
    PayableCategoryResponse,
)


router = APIRouter(prefix="/stores/{store_id}/payables/categories", tags=["Payables Categories"])

@router.post("", response_model=PayableCategoryResponse, status_code=201)
def create_category(payload: PayableCategoryCreate, store: GetStoreDep, db: GetDBDep):
    return payable_category_service.create(db, store, payload)

@router.get("", response_model=list[PayableCategoryResponse])
def list_categories(store: GetStoreDep, db: GetDBDep):
    return payable_category_service.list_by_store(db, store.id)

@router.get("/{category_id}", response_model=PayableCategoryResponse)
def get_category(category_id: int, store: GetStoreDep, db: GetDBDep):
    category = payable_category_service.get_by_id(db, category_id, store.id)
    if not category:
        raise HTTPException(status_code=404, detail="Category not found")
    return category

@router.patch("/{category_id}", response_model=PayableCategoryResponse)
def update_category(category_id: int, payload: PayableCategoryUpdate, store: GetStoreDep, db: GetDBDep):
    category = payable_category_service.get_by_id(db, category_id, store.id)
    if not category:
        raise HTTPException(status_code=404, detail="Category not found")
    return payable_category_service.update(db, category, payload)

@router.delete("/{category_id}", status_code=204)
def delete_category(category_id: int, store: GetStoreDep, db: GetDBDep):
    category = payable_category_service.get_by_id(db, category_id, store.id)
    if not category:
        raise HTTPException(status_code=404, detail="Category not found")
    payable_category_service.delete(db, category)
    return