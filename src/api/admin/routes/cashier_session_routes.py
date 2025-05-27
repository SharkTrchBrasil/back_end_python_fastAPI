from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func


from src.api.admin.schemas.cash_session import (
    CashierSessionUpdate,
    CashierSessionOut, CashierSessionCreate,

)
from src.api.admin.schemas.cash_transaction import CashierTransactionOut
from src.core.database import GetDBDep
from src.core.dependencies import GetStoreDep
from src.core.helpers.enums import CashierTransactionType, PaymentMethod
from src.core.models import CashierSession, CashierTransaction

router = APIRouter(prefix="/stores/{store_id}/cashier-sessions", tags=["Sessões de Caixa"])


@router.post("", response_model=CashierSessionOut)
def open_cash(payload: CashierSessionCreate, db: GetDBDep, store: GetStoreDep):
    existing = db.query(CashierSession).filter_by(store_id=store.id, status="open").first()
    if existing:
        raise HTTPException(status_code=400, detail="Já existe um caixa aberto")

    session = CashierSession(
        store_id=store.id,
        user_opened_id=payload.user_opened_id,
        opening_amount=payload.opening_amount,
        status="open",
        opened_at=datetime.utcnow()
    )
    db.add(session)
    db.commit()
    db.refresh(session)

    if payload.opening_amount > 0:
        movement = CashierTransaction(
            store_id=store.id,
            cashier_session_id=session.id,
            type='in',
            amount=payload.opening_amount,
            note='Saldo inicial do caixa',
            created_at=datetime.utcnow(),
        )
        db.add(movement)
        db.commit()

    return session

@router.get("/{id}", response_model=CashierSessionOut)
def get_session(id: int, db: GetDBDep, store: GetStoreDep):
    session = db.query(CashierSession).filter_by(id=id, store_id=store.id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Sessão não encontrada ou não pertence à loja")
    return session

@router.get("", response_model=list[CashierSessionOut])
def list_sessions(db: GetDBDep, store: GetStoreDep):
    return db.query(CashierSession).filter_by(store_id=store.id).all()

@router.put("/{id}", response_model=CashierSessionOut)
def update_session(id: int, data: CashierSessionUpdate, db: GetDBDep, store: GetStoreDep):
    session = db.query(CashierSession).filter_by(id=id, store_id=store.id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Sessão não encontrada ou não pertence à loja")

    for key, value in data.dict(exclude_unset=True).items():
        setattr(session, key, value)
    db.commit()
    db.refresh(session)
    return session

@router.delete("/{id}")
def delete_session(id: int, db: GetDBDep, store: GetStoreDep):
    session = db.query(CashierSession).filter_by(id=id, store_id=store.id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Sessão não encontrada ou não pertence à loja")

    db.delete(session)
    db.commit()
    return {"detail": "Sessão removida com sucesso"}


@router.get("/{id}/balance")
def get_session_balance(id: int, db: GetDBDep, store: GetStoreDep):
    session = db.query(CashierSession).filter_by(id=id, store_id=store.id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Sessão não encontrada")

    in_total = db.query(CashierTransaction).filter_by(cashier_session_id=id, movement_type="IN").with_entities(
        func.coalesce(func.sum(CashierTransaction.amount), 0)).scalar()

    out_total = db.query(CashierTransaction).filter_by(cashier_session_id=id, movement_type="OUT").with_entities(
        func.coalesce(func.sum(CashierTransaction.amount), 0)).scalar()

    balance = float(in_total) - float(out_total)
    return {"balance": balance}


@router.get("/{id}/transactions", response_model=list[CashierTransactionOut])
def list_session_transactions(id: int, db: GetDBDep, store: GetStoreDep):
    session = db.query(CashierSession).filter_by(id=id, store_id=store.id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Sessão não encontrada")

    return db.query(CashierTransaction).filter_by(cashier_session_id=id).all()




# Fechar o caixa
@router.post("/{id}/close", response_model=CashierSessionOut)
def close_cash(id: int, db: GetDBDep, store: GetStoreDep):
    session = db.query(CashierSession).filter_by(id=id, store_id=store.id).first()
    if not session or session.status != "open":
        raise HTTPException(status_code=404, detail="Sessão não encontrada ou já está fechada")

    session.status = "closed"
    session.closed_at = datetime.utcnow()
    db.commit()
    db.refresh(session)
    return session

# Adicionar dinheiro no caixa (ex: reforço)
@router.post("/{id}/add-cash", response_model=CashierTransactionOut)
def add_cash(
    id: int,
    amount: float,
    description: str = "Entrada de dinheiro manual",
    db: GetDBDep = Depends(GetDBDep),
    store: GetStoreDep = Depends(GetStoreDep)
):
    session = db.query(CashierSession).filter_by(id=id, store_id=store.id, status="open").first()
    if not session:
        raise HTTPException(status_code=404, detail="Sessão não encontrada ou já está fechada")

    transaction = CashierTransaction(
        cashier_session_id=id,
        type=CashierTransactionType.INFLOW,
        amount=amount,
        description=description,
        payment_method=PaymentMethod.CASH
    )
    db.add(transaction)
    db.commit()
    db.refresh(transaction)
    return transaction

# Remover dinheiro do caixa (ex: sangria)
@router.post("/{id}/remove-cash", response_model=CashierTransactionOut)
def remove_cash(
    id: int,
    amount: float,
    description: str = "Saída de dinheiro manual",
    db: GetDBDep = Depends(GetDBDep),
    store: GetStoreDep = Depends(GetStoreDep)
):
    session = db.query(CashierSession).filter_by(id=id, store_id=store.id, status="open").first()
    if not session:
        raise HTTPException(status_code=404, detail="Sessão não encontrada ou já está fechada")

    transaction = CashierTransaction(
        cashier_session_id=id,
        type=CashierTransactionType.OUTFLOW,
        amount=amount,
        description=description,
        payment_method=PaymentMethod.CASH
    )
    db.add(transaction)
    db.commit()
    db.refresh(transaction)
    return transaction


@router.get("/{id}/payment-summary")
def get_payment_summary(id: int, db: GetDBDep, store: GetStoreDep):
    # Verifica se sessão existe
    session = db.query(CashierSession).filter_by(id=id, store_id=store.id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Sessão não encontrada")

    # Consulta resumo por método de pagamento, soma valores IN
    result = (
        db.query(
            CashierTransaction.payment_method,
            func.coalesce(func.sum(CashierTransaction.amount), 0)
        )
        .filter_by(cashier_session_id=id, type=CashierTransactionType.INFLOW)
        .group_by(CashierTransaction.payment_method)
        .all()
    )

    summary = {payment_method.value: float(amount) for payment_method, amount in result}
    return summary
