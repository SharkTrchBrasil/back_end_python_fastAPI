from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import func, and_, cast, String

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

    # 🔎 Buscar total de vendas EM DINHEIRO
    total_cash_sales = db.query(func.sum(CashierTransaction.amount)).filter(
        CashierTransaction.cashier_session_id == session.id,
        CashierTransaction.type == CashierTransactionType.SALE,  # ou Enum, se estiver usando
        CashierTransaction.payment_method_id == 1  # 1 = ID do dinheiro (ajuste se for diferente)
    ).scalar() or 0.0

    # 🧮 Calcular saldo real disponível
    session.available_cash = (
        (session.opening_amount or 0) +
        (session.cash_added or 0) +
        total_cash_sales -
        (session.cash_removed or 0)
    )

    # Adicionar ao objeto (mesmo que não esteja no banco, o FastAPI envia junto se estiver no schema)
    session.total_cash_sales = total_cash_sales

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
        user_opened_id=user.id,
        opening_amount=payload.opening_amount,
        opened_at=datetime.now(timezone.utc),
        status="open",
        notes=payload.notes
    )
    db.add(session)
    db.commit()
    db.refresh(session)

    if payload.opening_amount > 0:
        # ✅ Validação do método de pagamento
        payment_method = db.query(StorePaymentMethods).filter_by(
            id=payload.payment_method_id,
            store_id=store.id
        ).first()

        if not payment_method:
            raise HTTPException(status_code=400, detail="Método de pagamento inválido para esta loja")

        movement = CashierTransaction(
            cashier_session_id=session.id,
            type=CashierTransactionType.INFLOW,
            amount=payload.opening_amount,
            description='Saldo inicial do caixa',
            payment_method_id=payload.payment_method_id,
            created_at=datetime.now(timezone.utc)
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
    payment_method_id: int


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
        payment_method_id=req.payment_method_id
    )

    # Atualiza valor em caixa
    session.cash_added += req.amount

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
        payment_method_id=req.payment_method_id
    )

    # Atualiza valor em caixa
    session.cash_removed += req.amount

    db.add(transaction)
    db.commit()
    db.refresh(transaction)
    return transaction


@router.get("/{id}/payment-summary")
def get_payment_summary(id: int, db: GetDBDep, store: GetStoreDep):
    # Obter os métodos de pagamento ativos da loja
    store_payment_methods = db.query(StorePaymentMethods).filter(
        StorePaymentMethods.store_id == store.id,
        StorePaymentMethods.is_active == True,
        StorePaymentMethods.active_on_counter == True
    ).all()

    # Criar um mapeamento de id para nome personalizado
    custom_names_map = {pm.id: pm.custom_name for pm in store_payment_methods}

    # Obter totais por método de pagamento baseado no ID
    transaction_sums = (
        db.query(
            CashierTransaction.payment_method_id,
            func.coalesce(func.sum(CashierTransaction.amount), 0).label("total")
        )
        .filter(
            CashierTransaction.cashier_session_id == id,
            CashierTransaction.type == CashierTransactionType.INFLOW
        )
        .group_by(CashierTransaction.payment_method_id)
        .all()
    )

    # Montar dicionário com os totais usando os nomes personalizados
    final_summary = {}
    for pm in store_payment_methods:
        total = next(
            (float(ts.total) for ts in transaction_sums if ts.payment_method_id == pm.id),
            0.0
        )
        final_summary[pm.custom_name] = total

    return final_summary