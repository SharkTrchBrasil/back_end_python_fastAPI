from datetime import date
from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks, Query

from src.api.admin.services.receivable_service import receivable_service
# Adapte os imports para a estrutura do seu projeto
from src.core.database import GetDBDep
from src.core.dependencies import GetStoreDep
from src.api.schemas.receivable import ReceivableCreate, ReceivableUpdate, ReceivableResponse

from src.api.admin.socketio.emitters import admin_emit_financials_updated

router = APIRouter(prefix="/stores/{store_id}/receivables", tags=["Receivables"])


@router.post("", response_model=ReceivableResponse, status_code=201)
def create_receivable(
        payload: ReceivableCreate,
        store: GetStoreDep,
        db: GetDBDep,
        background_tasks: BackgroundTasks,
):
    receivable = receivable_service.create_receivable(db, store, payload)
    # Dispara o evento para atualizar a UI em tempo real
    background_tasks.add_task(admin_emit_financials_updated, db=db, store_id=store.id)
    return receivable


@router.get("", response_model=list[ReceivableResponse])
def list_receivables(
        store: GetStoreDep,
        db: GetDBDep,
        skip: int = 0,
        limit: int = 100,
):
    # Lembre-se de adicionar mais filtros aqui (status, cliente, etc.) se precisar
    return receivable_service.list_receivables(db, store.id, skip, limit)


@router.patch("/{receivable_id}", response_model=ReceivableResponse)
def update_receivable(
        receivable_id: int,
        payload: ReceivableUpdate,
        store: GetStoreDep,
        db: GetDBDep,
        background_tasks: BackgroundTasks,
):
    receivable = receivable_service.get_receivable_by_id(db, receivable_id, store.id)
    if not receivable:
        raise HTTPException(status_code=404, detail="Receivable not found")

    updated_receivable = receivable_service.update_receivable(db, receivable, payload)
    # Dispara o evento para atualizar a UI
    background_tasks.add_task(admin_emit_financials_updated, db=db, store_id=store.id)
    return updated_receivable


@router.delete("/{receivable_id}", status_code=204)
def delete_receivable(
        receivable_id: int,
        store: GetStoreDep,
        db: GetDBDep,
        background_tasks: BackgroundTasks,
):
    receivable = receivable_service.get_receivable_by_id(db, receivable_id, store.id)
    if not receivable:
        raise HTTPException(status_code=404, detail="Receivable not found")

    receivable_service.delete_receivable(db, receivable)
    # Dispara o evento para atualizar a UI
    background_tasks.add_task(admin_emit_financials_updated, db=db, store_id=store.id)
    return


@router.post("/{receivable_id}/receive", response_model=ReceivableResponse)
def mark_as_received(
        receivable_id: int,
        store: GetStoreDep,
        db: GetDBDep,
        background_tasks: BackgroundTasks,
):
    receivable = receivable_service.get_receivable_by_id(db, receivable_id, store.id)
    if not receivable:
        raise HTTPException(status_code=404, detail="Receivable not found")

    received_receivable = receivable_service.mark_as_received(db, receivable)
    # Dispara o evento para atualizar a UI
    background_tasks.add_task(admin_emit_financials_updated, db=db, store_id=store.id)
    return received_receivable