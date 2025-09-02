from fastapi import APIRouter, HTTPException


from src.api.schemas.financial.cash_transaction import (
    CashierTransactionOut,
    CashierTransactionCreate,
    CashierTransactionUpdate,
)
from src.core.database import GetDBDep
from src.core.dependencies import GetStoreDep
from src.core.models import CashierTransaction, CashierSession

router = APIRouter(
    prefix="/stores/{store_id}/cashier_transactions",
    tags=["Movimentações de Caixa"]
)

@router.post("/", response_model=CashierTransactionOut)
def create_transaction(
    data: CashierTransactionCreate,
    db: GetDBDep,
    store: GetStoreDep,
):
    # Verifica se a sessão pertence à loja (sem cash_register agora)
    session = db.query(CashierSession).filter_by(id=data.cashier_session_id, store_id=store.id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Sessão não encontrada ou não pertence à loja")

    transaction = CashierTransaction(**data.dict())
    db.add(transaction)
    db.commit()
    db.refresh(transaction)
    return transaction


@router.get("/{id}", response_model=CashierTransactionOut)
def get_transaction(id: int, db: GetDBDep, store: GetStoreDep):
    transaction = (
        db.query(CashierTransaction)
        .join(CashierTransaction.cashier_session)
        .filter(CashierTransaction.id == id, CashierSession.store_id == store.id)
        .first()
    )
    if not transaction:
        raise HTTPException(status_code=404, detail="Movimentação não encontrada ou não pertence à loja")
    return transaction


@router.get("/", response_model=list[CashierTransactionOut])
def list_transactions(db: GetDBDep, store: GetStoreDep):
    return (
        db.query(CashierTransaction)
        .join(CashierTransaction.cashier_session)
        .filter(CashierSession.store_id == store.id)
        .all()
    )


@router.put("/{id}", response_model=CashierTransactionOut)
def update_transaction(id: int, data: CashierTransactionUpdate, db: GetDBDep, store: GetStoreDep):
    transaction = (
        db.query(CashierTransaction)
        .join(CashierTransaction.cashier_session)
        .filter(CashierTransaction.id == id, CashierSession.store_id == store.id)
        .first()
    )
    if not transaction:
        raise HTTPException(status_code=404, detail="Movimentação não encontrada ou não pertence à loja")

    for key, value in data.dict(exclude_unset=True).items():
        setattr(transaction, key, value)
    db.commit()
    db.refresh(transaction)
    return transaction


@router.delete("/{id}")
def delete_transaction(id: int, db: GetDBDep, store: GetStoreDep):
    transaction = (
        db.query(CashierTransaction)
        .join(CashierTransaction.cashier_session)
        .filter(CashierTransaction.id == id, CashierSession.store_id == store.id)
        .first()
    )
    if not transaction:
        raise HTTPException(status_code=404, detail="Movimentação não encontrada ou não pertence à loja")

    db.delete(transaction)
    db.commit()
    return {"detail": "Movimentação removida com sucesso"}
