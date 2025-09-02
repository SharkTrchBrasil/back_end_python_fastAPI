from fastapi import APIRouter, HTTPException, BackgroundTasks

from src.api.admin.services.receivable_service import receivable_category_service
# Adapte os imports para a estrutura do seu projeto
from src.core.database import GetDBDep
from src.core.dependencies import GetStoreDep
from src.api.schemas.financial.receivable import (
    ReceivableCategoryCreate,
    ReceivableCategoryUpdate,
    ReceivableCategoryResponse,
)

from src.api.admin.socketio.emitters import admin_emit_financials_updated

router = APIRouter(prefix="/stores/{store_id}/receivables/categories", tags=["Receivables Categories"])


@router.post("", response_model=ReceivableCategoryResponse, status_code=201)
def create_category(
        payload: ReceivableCategoryCreate,
        store: GetStoreDep,
        db: GetDBDep,
        background_tasks: BackgroundTasks,
):
    category = receivable_category_service.create(db, store, payload)
    # Dispara o evento para atualizar a lista de categorias no frontend
    background_tasks.add_task(admin_emit_financials_updated, db=db, store_id=store.id)
    return category


@router.get("", response_model=list[ReceivableCategoryResponse])
def list_categories(store: GetStoreDep, db: GetDBDep):
    return receivable_category_service.list_by_store(db, store.id)


@router.patch("/{category_id}", response_model=ReceivableCategoryResponse)
def update_category(
        category_id: int,
        payload: ReceivableCategoryUpdate,
        store: GetStoreDep,
        db: GetDBDep,
        background_tasks: BackgroundTasks,
):
    category = receivable_category_service.get_by_id(db, category_id, store.id)
    if not category:
        raise HTTPException(status_code=404, detail="Category not found")

    updated_category = receivable_category_service.update(db, category, payload)
    # Dispara o evento para atualizar a lista de categorias no frontend
    background_tasks.add_task(admin_emit_financials_updated, db=db, store_id=store.id)
    return updated_category


@router.delete("/{category_id}", status_code=204)
def delete_category(
        category_id: int,
        store: GetStoreDep,
        db: GetDBDep,
        background_tasks: BackgroundTasks,
):
    category = receivable_category_service.get_by_id(db, category_id, store.id)
    if not category:
        raise HTTPException(status_code=404, detail="Category not found")

    receivable_category_service.delete(db, category)
    # Dispara o evento para atualizar a lista de categorias no frontend
    background_tasks.add_task(admin_emit_financials_updated, db=db, store_id=store.id)
    return