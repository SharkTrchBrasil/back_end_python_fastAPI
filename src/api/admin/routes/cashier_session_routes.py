from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import func, and_

from src.api.admin.schemas.cash_session import (
    CashierSessionUpdate,
    CashierSessionOut, CashierSessionCreate,

)
from src.api.admin.schemas.cash_transaction import CashierTransactionOut
from src.core.database import GetDBDep
from src.core.dependencies import GetStoreDep, GetCurrentUserDep
from src.core.helpers.enums import CashierTransactionType, PaymentMethod
from src.core.models import CashierSession, CashierTransaction, StorePaymentMethods

router = APIRouter(prefix="/stores/{store_id}/cashier-sessions", tags=["Sessões de Caixa"])

@router.get("/current", response_model=CashierSessionOut)
def get_current_cashier_session(
    db: GetDBDep,
    store: GetStoreDep
):
    session = db.query(CashierSession).filter(
        and_(
            CashierSession.store_id == store.id,
            CashierSession.status == 'open'
        )
    ).first()

    if not session:
        raise HTTPException(status_code=404, detail="Nenhuma sessão de caixa aberta encontrada.")

    return session
@router.post("", response_model=CashierSessionOut)
def open_cash(
    payload: CashierSessionCreate,
    db: GetDBDep,
    store: GetStoreDep,
    user: GetCurrentUserDep
):
    existing = db.query(CashierSession).filter_by(store_id=store.id, status="open").first()
    if existing:
        raise HTTPException(status_code=400, detail="Já existe um caixa aberto")

    session = CashierSession(
        store_id=store.id,
        user_opened_id=user.id,  # Pega do contexto
        opening_amount=payload.opening_amount,
        opened_at=datetime.now(timezone.utc),
        status="open",
        notes=payload.notes
    )
    db.add(session)
    db.commit()
    db.refresh(session)


    if payload.opening_amount > 0:
        movement = CashierTransaction(
            cashier_session_id=session.id,
            type=CashierTransactionType.INFLOW,
            amount=payload.opening_amount,
            description='Saldo inicial do caixa',
            created_at=datetime.now(timezone.utc),
            order_id=None,
            payment_method=PaymentMethod.CASH,
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
    session.closed_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(session)
    return session




class AddCashRequest(BaseModel):
    amount: float
    description: str

@router.post("/{id}/add-cash", response_model=CashierTransactionOut)
def add_cash(
    id: int,
    req: AddCashRequest,
    db: GetDBDep,
    store: GetStoreDep,
):
    session = db.query(CashierSession).filter_by(id=id, store_id=store.id, status="open").first()
    if not session:
        raise HTTPException(status_code=404, detail="Sessão não encontrada ou já está fechada")

    transaction = CashierTransaction(
        cashier_session_id=id,
        type=CashierTransactionType.INFLOW,
        amount=req.amount,
        description=req.description,
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
    req: AddCashRequest,
    db: GetDBDep,
    store: GetStoreDep
):
    session = db.query(CashierSession).filter_by(id=id, store_id=store.id, status="open").first()
    if not session:
        raise HTTPException(status_code=404, detail="Sessão não encontrada ou já está fechada")

    transaction = CashierTransaction(
        cashier_session_id=id,
        type=CashierTransactionType.OUTFLOW,
        amount=req.amount,
        description=req.description,
        payment_method=PaymentMethod.CASH
    )
    db.add(transaction)
    db.commit()
    db.refresh(transaction)
    return transaction



@router.get("/{id}/payment-summary")
def get_payment_summary(id: int, db: GetDBDep, store: GetStoreDep):
    # Verify session existence
    session = db.query(CashierSession).filter_by(id=id, store_id=store.id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    # --- MODIFIED QUERY ---
    result = (
        db.query(
            StorePaymentMethods.custom_name, # <--- Select the custom_name
            func.coalesce(func.sum(CashierTransaction.amount), 0)
        )
        .join(
            StorePaymentMethods,
            # Join CashierTransaction with StorePaymentMethods
            # on the condition that CashierTransaction.payment_method
            # matches StorePaymentMethods.payment_type
            # AND StorePaymentMethods.store_id matches the current store
            (CashierTransaction.payment_method == StorePaymentMethods.payment_type) &
            (StorePaymentMethods.store_id == store.id) # IMPORTANT: Filter payment methods by store
        )
        .filter(
            CashierTransaction.cashier_session_id == id,
            CashierTransaction.type == CashierTransactionType.INFLOW
        )
        .group_by(
            StorePaymentMethods.custom_name # <--- Group by custom_name for the summary
            # Note: If two *different* payment types (e.g., "Cash" and "OnlinePay") happened to have the same custom_name ("Payment"),
            # they would be summed together. If you need absolute uniqueness for the key,
            # you might need to group by StorePaymentMethods.id and then use custom_name.
            # For distinct custom names, grouping by custom_name is typically fine.
        )
        .all()
    )

    summary = {str(custom_name): float(amount) for custom_name, amount in result}

    # You might want to get all active payment methods for the store
    # and initialize their sums to 0 if no transactions occurred for them,
    # then update with actual transaction sums.
    all_active_payment_methods = db.query(StorePaymentMethods).filter(
        StorePaymentMethods.store_id == store.id,
        StorePaymentMethods.is_active == True,
        # Consider active_on_counter as well if this is for counter sales
        StorePaymentMethods.active_on_counter == True
    ).all()

    final_summary = {}
    for pm in all_active_payment_methods:
        final_summary[pm.custom_name] = summary.get(pm.custom_name, 0.0) # Initialize with 0 or the sum from transactions

    return final_summary
