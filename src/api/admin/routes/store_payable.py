from datetime import date

from fastapi import APIRouter, HTTPException
from sqlalchemy.orm import Query

from src.api.admin.services.payable_service import payable_service
from src.api.schemas.store_payable import PayableUpdate, PayableResponse, PayableCreate
from src.core.database import GetDBDep
from src.core.dependencies import GetStoreDep
from src.core.models import StorePayable
from src.core.utils.enums import PayableStatus

router = APIRouter(prefix="/stores/{store_id}/payables", tags=["Payables"])

@router.post("", response_model=PayableResponse, status_code=201)
def create_payable(payload: PayableCreate, db: GetDBDep, store: GetStoreDep):
    # ✅ LÓGICA MOVIDA: Apenas chama o service
    return payable_service.create_payable(db, store, payload)

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
def update_payable(payable_id: int, payload: PayableUpdate, db: GetDBDep, store: GetStoreDep):
    payable = payable_service.get_payable_by_id(db, payable_id, store.id)
    if not payable:
        raise HTTPException(status_code=404, detail="Payable not found")

    # ✅ CORREÇÃO: payload.dict() é da v1, model_dump() é da v2
    # Essa lógica agora está dentro do service, então a chamada fica mais limpa
    return payable_service.update_payable(db, payable, payload)

@router.delete("/{payable_id}", status_code=204)
def delete_payable(payable_id: int, db: GetDBDep, store: GetStoreDep):
    payable = payable_service.get_payable_by_id(db, payable_id, store.id)
    if not payable:
        raise HTTPException(status_code=404, detail="Payable not found")
    payable_service.delete_payable(db, payable)
    return



# Nova rota para marcar como pago (mais semântico usar POST para ações)
@router.post("/{payable_id}/pay", response_model=PayableResponse)
def mark_payable_as_paid(
        payable_id: int,
        store: GetStoreDep,
        db: GetDBDep,
):
    payable = payable_service.get_payable_by_id(db, payable_id, store.id)
    if not payable:
        raise HTTPException(status_code=404, detail="Payable not found")

    return payable_service.mark_as_paid(db, payable)


