from datetime import date

from fastapi import APIRouter, HTTPException, Query, BackgroundTasks

from src.api.admin.services.payable_service import payable_service
from src.api.admin.socketio.emitters import admin_emit_dashboard_payables_data_updated, admin_emit_financials_updated
from src.api.schemas.store_payable import PayableUpdate, PayableResponse, PayableCreate
from src.core.database import GetDBDep
from src.core.dependencies import GetStoreDep

from src.core.utils.enums import PayableStatus

router = APIRouter(prefix="/stores/{store_id}/payables", tags=["Payables"])


@router.post("", response_model=PayableResponse, status_code=201)
def create_payable(
        payload: PayableCreate,
        db: GetDBDep,
        store: GetStoreDep,

        background_tasks: BackgroundTasks,
):
    # O serviço é chamado normalmente
    payable = payable_service.create_payable(db, store, payload)

    background_tasks.add_task(admin_emit_dashboard_payables_data_updated, db=db, store_id=store.id)
    background_tasks.add_task(admin_emit_financials_updated, db=db, store_id=store.id)

    return payable


@router.get("", response_model=list[PayableResponse])
def list_payables(
        store: GetStoreDep, db: GetDBDep,
        status: PayableStatus | None = Query(None),
        supplier_id: int | None = Query(None),
        start_date: date | None = Query(None),
        end_date: date | None = Query(None),
        # ✅ ADIÇÃO: Paginação
        skip: int = 0, limit: int = 100,
):
    return payable_service.list_payables(db, store.id, status, supplier_id, start_date, end_date, skip, limit)


@router.get("/{payable_id}", response_model=PayableResponse)
def get_payable(payable_id: int, db: GetDBDep, store: GetStoreDep):
    # ✅ LÓGICA MOVIDA: Usa o service para buscar o objeto
    payable = payable_service.get_payable_by_id(db, payable_id, store.id)
    if not payable:
        raise HTTPException(status_code=404, detail="Payable not found")
    return payable


@router.patch("/{payable_id}", response_model=PayableResponse)
def update_payable(
        payable_id: int,
        payload: PayableUpdate,
        db: GetDBDep,
        store: GetStoreDep,
        background_tasks: BackgroundTasks,
):
    payable = payable_service.get_payable_by_id(db, payable_id, store.id)
    if not payable:
        raise HTTPException(status_code=404, detail="Payable not found")

    # ✅ CORREÇÃO: Primeiro executa a atualização no banco de dados
    updated_payable = payable_service.update_payable(db, payable, payload)

    # ✅ Depois, com os dados já salvos, agenda a notificação
    background_tasks.add_task(admin_emit_dashboard_payables_data_updated, db=db, store_id=store.id)
    background_tasks.add_task(admin_emit_financials_updated, db=db, store_id=store.id)

    return updated_payable


@router.delete("/{payable_id}", status_code=204)
def delete_payable(payable_id: int, db: GetDBDep, store: GetStoreDep, background_tasks: BackgroundTasks, ):
    payable = payable_service.get_payable_by_id(db, payable_id, store.id)
    if not payable:
        raise HTTPException(status_code=404, detail="Payable not found")
    payable_service.delete_payable(db, payable)

    background_tasks.add_task(admin_emit_dashboard_payables_data_updated, db=db, store_id=store.id)
    background_tasks.add_task(admin_emit_financials_updated, db=db, store_id=store.id)

    return


@router.post("/{payable_id}/pay", response_model=PayableResponse)
def mark_payable_as_paid(
        payable_id: int,
        store: GetStoreDep,
        db: GetDBDep,
        background_tasks: BackgroundTasks,
):
    payable = payable_service.get_payable_by_id(db, payable_id, store.id)
    if not payable:
        raise HTTPException(status_code=404, detail="Payable not found")

    # ✅ CORREÇÃO: Primeiro marca como pago no banco de dados
    paid_payable = payable_service.mark_as_paid(db, payable)

    # ✅ Depois, com os dados já salvos, agenda a notificação
    background_tasks.add_task(admin_emit_dashboard_payables_data_updated, db=db, store_id=store.id)
    background_tasks.add_task(admin_emit_financials_updated, db=db, store_id=store.id)

    return paid_payable
