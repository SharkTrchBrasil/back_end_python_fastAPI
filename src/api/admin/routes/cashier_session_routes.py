# src/api/admin/routes/cashier_session_routes.py

from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy import func, and_

from src.api.schemas.financial.cash_session import (
    CashierSessionUpdate,
    CashierSessionOut,
    CashierSessionCreate,
)
from src.api.schemas.financial.cash_transaction import CashierTransactionOut
from src.core.database import GetDBDep
from src.core.dependencies import GetStoreDep, GetCurrentUserDep, GetAuditLoggerDep
from src.core.models import CashierSession, CashierTransaction
from src.core.utils.enums import CashierTransactionType, AuditAction, AuditEntityType

router = APIRouter(prefix="/stores/{store_id}/cashier-sessions", tags=["Sessões de Caixa"])


# ═══════════════════════════════════════════════════════════════
# ROTA DE LEITURA - SEM AUDITORIA
# ═══════════════════════════════════════════════════════════════

@router.get("/current", response_model=CashierSessionOut)
def get_current_cashier_session(
        db: GetDBDep,
        store: GetStoreDep
):
    """Retorna a sessão de caixa aberta atual."""
    session = db.query(CashierSession).filter(
        and_(
            CashierSession.store_id == store.id,
            CashierSession.status == 'open'
        )
    ).first()

    if not session:
        raise HTTPException(status_code=404, detail="Nenhuma sessão de caixa aberta encontrada.")

    return session


# ═══════════════════════════════════════════════════════════════
# 🔥 PONTO VITAL 1: ABRIR CAIXA
# ═══════════════════════════════════════════════════════════════

@router.post("", response_model=CashierSessionOut)
def open_cash(
        request: Request,  # ✅ ADICIONAR
        payload: CashierSessionCreate,
        db: GetDBDep,
        store: GetStoreDep,
        user: GetCurrentUserDep,
        audit: GetAuditLoggerDep  # ✅ ADICIONAR AUDITORIA
):
    """
    ✅ Abre uma nova sessão de caixa com auditoria completa
    """

    # Verifica se já existe um caixa aberto
    existing = db.query(CashierSession).filter_by(
        store_id=store.id,
        status="open"
    ).first()

    if existing:
        # ✅ LOG DE TENTATIVA FALHADA
        audit.log_failed_action(
            action=AuditAction.OPEN_CASHIER,
            entity_type=AuditEntityType.CASHIER_SESSION,
            error=f"Tentativa de abrir caixa com sessão já aberta (ID: {existing.id})"
        )
        db.commit()

        raise HTTPException(status_code=400, detail="Já existe um caixa aberto")

    # Cria nova sessão
    session = CashierSession(
        store_id=store.id,
        user_opened_id=user.id,
        opening_amount=payload.opening_amount,
        opened_at=datetime.now(timezone.utc),
        status="open",
    )
    db.add(session)
    db.flush()  # Para obter o ID antes do commit

    # ✅ LOG DE ABERTURA BEM-SUCEDIDA
    audit.log(
        action=AuditAction.OPEN_CASHIER,
        entity_type=AuditEntityType.CASHIER_SESSION,
        entity_id=session.id,
        changes={
            "store_name": store.name,
            "user_name": user.name,
            "opening_amount": float(payload.opening_amount),
            "opened_at": session.opened_at.isoformat()
        },
        description=f"Caixa aberto por '{user.name}' com saldo inicial de R$ {payload.opening_amount:.2f}"
    )

    db.commit()
    db.refresh(session)

    return session


# ═══════════════════════════════════════════════════════════════
# 🔥 PONTO VITAL 2: FECHAR CAIXA
# ═══════════════════════════════════════════════════════════════

@router.post("/{id}/close", response_model=CashierSessionOut)
def close_cash(
        request: Request,  # ✅ ADICIONAR
        id: int,
        data: CashierSessionUpdate,
        db: GetDBDep,
        store: GetStoreDep,
        user: GetCurrentUserDep,
        audit: GetAuditLoggerDep  # ✅ ADICIONAR AUDITORIA
):
    """
    ✅ Fecha uma sessão de caixa com auditoria de divergências
    """

    session = db.query(CashierSession).filter_by(
        id=id,
        store_id=store.id
    ).first()

    if not session or session.status != "open":
        # ✅ LOG DE TENTATIVA FALHADA
        audit.log_failed_action(
            action=AuditAction.CLOSE_CASHIER,
            entity_type=AuditEntityType.CASHIER_SESSION,
            entity_id=id,
            error=f"Sessão não encontrada ou já está fechada (status: {session.status if session else 'N/A'})"
        )
        db.commit()

        raise HTTPException(
            status_code=404,
            detail="Sessão não encontrada ou já está fechada"
        )

    # Captura valores antes de fechar
    old_values = {
        "status": session.status,
        "opened_at": session.opened_at.isoformat(),
        "opening_amount": float(session.opening_amount),
        "cash_added": float(session.cash_added or 0),
        "cash_removed": float(session.cash_removed or 0)
    }

    # Atualiza a sessão
    session.status = "closed"
    session.user_closed_id = user.id
    session.closed_at = datetime.now(timezone.utc)
    session.expected_amount = data.expected_amount
    session.informed_amount = data.informed_amount
    session.cash_difference = data.cash_difference

    # ✅ Detecta divergências (diferença entre esperado e informado)
    has_discrepancy = abs(session.cash_difference) > 0.01  # Margem de R$ 0,01

    # ✅ LOG DE FECHAMENTO
    audit.log(
        action=AuditAction.CLOSE_CASHIER,
        entity_type=AuditEntityType.CASHIER_SESSION,
        entity_id=session.id,
        changes={
            "store_name": store.name,
            "user_opened": db.get(session.user_opened_id).name if session.user_opened_id else "Desconhecido",
            "user_closed": user.name,
            "opened_at": old_values["opened_at"],
            "closed_at": session.closed_at.isoformat(),
            "opening_amount": old_values["opening_amount"],
            "cash_added": old_values["cash_added"],
            "cash_removed": old_values["cash_removed"],
            "expected_amount": float(session.expected_amount),
            "informed_amount": float(session.informed_amount),
            "cash_difference": float(session.cash_difference),
            "has_discrepancy": has_discrepancy
        },
        description=(
            f"Caixa fechado por '{user.name}' - "
            f"Esperado: R$ {session.expected_amount:.2f} - "
            f"Informado: R$ {session.informed_amount:.2f} - "
            f"{'⚠️ DIVERGÊNCIA' if has_discrepancy else '✅ Sem divergência'}: R$ {session.cash_difference:.2f}"
        )
    )

    # ✅ LOG EXTRA SE HOUVER DIVERGÊNCIA SIGNIFICATIVA
    if has_discrepancy:
        audit.log(
            action=AuditAction.CASHIER_DISCREPANCY,
            entity_type=AuditEntityType.CASHIER_SESSION,
            entity_id=session.id,
            changes={
                "discrepancy_amount": float(session.cash_difference),
                "expected": float(session.expected_amount),
                "informed": float(session.informed_amount),
                "percentage": (
                            session.cash_difference / session.expected_amount * 100) if session.expected_amount > 0 else 0
            },
            description=f"⚠️ DIVERGÊNCIA NO CAIXA: R$ {session.cash_difference:.2f}"
        )

    db.commit()
    db.refresh(session)

    return session


# ═══════════════════════════════════════════════════════════════
# 🔥 PONTO VITAL 3: ADICIONAR DINHEIRO (REFORÇO/SANGRIA REVERSA)
# ═══════════════════════════════════════════════════════════════

class AddCashRequest(BaseModel):
    amount: float
    description: str
    payment_method_id: int


@router.post("/{id}/add-cash", response_model=CashierTransactionOut)
def add_cash(
        request: Request,  # ✅ ADICIONAR
        id: int,
        req: AddCashRequest,
        db: GetDBDep,
        store: GetStoreDep,
        user: GetCurrentUserDep,
        audit: GetAuditLoggerDep  # ✅ ADICIONAR AUDITORIA
):
    """
    ✅ Adiciona dinheiro ao caixa (reforço) com auditoria
    """

    session = db.query(CashierSession).filter_by(
        id=id,
        store_id=store.id,
        status="open"
    ).first()

    if not session:
        # ✅ LOG DE TENTATIVA FALHADA
        audit.log_failed_action(
            action=AuditAction.ADD_CASH,
            entity_type=AuditEntityType.CASHIER_SESSION,
            entity_id=id,
            error="Sessão não encontrada ou já está fechada"
        )
        db.commit()

        raise HTTPException(
            status_code=404,
            detail="Sessão não encontrada ou já está fechada"
        )

    # Validação de valor
    if req.amount <= 0:
        # ✅ LOG DE VALIDAÇÃO
        audit.log_failed_action(
            action=AuditAction.ADD_CASH,
            entity_type=AuditEntityType.CASHIER_SESSION,
            entity_id=id,
            error=f"Tentativa de adicionar valor inválido: R$ {req.amount}"
        )
        db.commit()

        raise HTTPException(
            status_code=400,
            detail="O valor deve ser positivo"
        )

    # Cria a transação
    transaction = CashierTransaction(
        cashier_session_id=id,
        type=CashierTransactionType.INFLOW,
        amount=req.amount,
        user_id=user.id,
        description=req.description,
        payment_method_id=req.payment_method_id
    )

    # Atualiza valor em caixa
    session.cash_added += req.amount

    db.add(transaction)
    db.flush()

    # ✅ LOG DE ADIÇÃO BEM-SUCEDIDA
    audit.log(
        action=AuditAction.ADD_CASH,
        entity_type=AuditEntityType.CASHIER_SESSION,
        entity_id=session.id,
        changes={
            "transaction_id": transaction.id,
            "store_name": store.name,
            "user_name": user.name,
            "amount": float(req.amount),
            "description": req.description,
            "payment_method_id": req.payment_method_id,
            "previous_cash_added": float(session.cash_added - req.amount),
            "new_cash_added": float(session.cash_added)
        },
        description=f"💵 Dinheiro adicionado ao caixa por '{user.name}': R$ {req.amount:.2f} - {req.description}"
    )

    db.commit()
    db.refresh(transaction)

    return transaction


# ═══════════════════════════════════════════════════════════════
# 🔥 PONTO VITAL 4: REMOVER DINHEIRO (SANGRIA)
# ═══════════════════════════════════════════════════════════════

@router.post("/{id}/remove-cash", response_model=CashierTransactionOut)
def remove_cash(
        request: Request,  # ✅ ADICIONAR
        id: int,
        req: AddCashRequest,
        db: GetDBDep,
        store: GetStoreDep,
        user: GetCurrentUserDep,
        audit: GetAuditLoggerDep  # ✅ ADICIONAR AUDITORIA
):
    """
    ✅ Remove dinheiro do caixa (sangria) com auditoria
    """

    session = db.query(CashierSession).filter_by(
        id=id,
        store_id=store.id,
        status="open"
    ).first()

    if not session:
        # ✅ LOG DE TENTATIVA FALHADA
        audit.log_failed_action(
            action=AuditAction.REMOVE_CASH,
            entity_type=AuditEntityType.CASHIER_SESSION,
            entity_id=id,
            error="Sessão não encontrada ou já está fechada"
        )
        db.commit()

        raise HTTPException(
            status_code=404,
            detail="Sessão não encontrada ou já está fechada"
        )

    # Validação de valor
    if req.amount <= 0:
        # ✅ LOG DE VALIDAÇÃO
        audit.log_failed_action(
            action=AuditAction.REMOVE_CASH,
            entity_type=AuditEntityType.CASHIER_SESSION,
            entity_id=id,
            error=f"Tentativa de remover valor inválido: R$ {req.amount}"
        )
        db.commit()

        raise HTTPException(
            status_code=400,
            detail="O valor deve ser positivo"
        )

    # Cria a transação
    transaction = CashierTransaction(
        cashier_session_id=id,
        type=CashierTransactionType.OUTFLOW,
        amount=req.amount,
        user_id=user.id,
        description=req.description,
        payment_method_id=req.payment_method_id
    )

    # Atualiza valor em caixa
    session.cash_removed += req.amount

    db.add(transaction)
    db.flush()

    # ✅ LOG DE REMOÇÃO BEM-SUCEDIDA
    audit.log(
        action=AuditAction.REMOVE_CASH,
        entity_type=AuditEntityType.CASHIER_SESSION,
        entity_id=session.id,
        changes={
            "transaction_id": transaction.id,
            "store_name": store.name,
            "user_name": user.name,
            "amount": float(req.amount),
            "description": req.description,
            "payment_method_id": req.payment_method_id,
            "previous_cash_removed": float(session.cash_removed - req.amount),
            "new_cash_removed": float(session.cash_removed)
        },
        description=f"💸 Sangria realizada por '{user.name}': R$ {req.amount:.2f} - {req.description}"
    )

    db.commit()
    db.refresh(transaction)

    return transaction


# ═══════════════════════════════════════════════════════════════
# ROTAS DE LEITURA - SEM AUDITORIA
# ═══════════════════════════════════════════════════════════════

@router.get("/{id}", response_model=CashierSessionOut)
def get_session(id: int, db: GetDBDep, store: GetStoreDep):
    """Busca uma sessão específica."""
    session = db.query(CashierSession).filter_by(id=id, store_id=store.id).first()
    if not session:
        raise HTTPException(
            status_code=404,
            detail="Sessão não encontrada ou não pertence à loja"
        )
    return session


@router.get("", response_model=list[CashierSessionOut])
def list_sessions(db: GetDBDep, store: GetStoreDep):
    """Lista todas as sessões de caixa da loja."""
    return db.query(CashierSession).filter_by(store_id=store.id).all()


@router.get("/{id}/balance")
def get_session_balance(id: int, db: GetDBDep, store: GetStoreDep):
    """Calcula o saldo atual da sessão."""
    session = db.query(CashierSession).filter_by(id=id, store_id=store.id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Sessão não encontrada")

    in_total = db.query(CashierTransaction).filter_by(
        cashier_session_id=id,
        movement_type="IN"
    ).with_entities(
        func.coalesce(func.sum(CashierTransaction.amount), 0)
    ).scalar()

    out_total = db.query(CashierTransaction).filter_by(
        cashier_session_id=id,
        movement_type="OUT"
    ).with_entities(
        func.coalesce(func.sum(CashierTransaction.amount), 0)
    ).scalar()

    balance = float(in_total) - float(out_total)
    return {"balance": balance}


@router.get("/{id}/transactions", response_model=list[CashierTransactionOut])
def list_session_transactions(id: int, db: GetDBDep, store: GetStoreDep):
    """Lista todas as transações de uma sessão."""
    session = db.query(CashierSession).filter_by(id=id, store_id=store.id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Sessão não encontrada")

    return db.query(CashierTransaction).filter_by(cashier_session_id=id).all()


# ═══════════════════════════════════════════════════════════════
# ROTAS DE ADMINISTRAÇÃO - COM AUDITORIA LEVE
# ═══════════════════════════════════════════════════════════════

@router.put("/{id}", response_model=CashierSessionOut)
def update_session(
        request: Request,  # ✅ ADICIONAR
        id: int,
        data: CashierSessionUpdate,
        db: GetDBDep,
        store: GetStoreDep,
        user: GetCurrentUserDep,
        audit: GetAuditLoggerDep  # ✅ ADICIONAR
):
    """
    ✅ Atualiza uma sessão de caixa (ajustes administrativos)
    """
    session = db.query(CashierSession).filter_by(id=id, store_id=store.id).first()
    if not session:
        raise HTTPException(
            status_code=404,
            detail="Sessão não encontrada ou não pertence à loja"
        )

    old_values = {
        "expected_amount": float(session.expected_amount) if session.expected_amount else None,
        "informed_amount": float(session.informed_amount) if session.informed_amount else None,
        "cash_difference": float(session.cash_difference) if session.cash_difference else None
    }

    for key, value in data.dict(exclude_unset=True).items():
        setattr(session, key, value)

    # ✅ LOG DE AJUSTE
    audit.log(
        action=AuditAction.CASHIER_ADJUSTMENT,
        entity_type=AuditEntityType.CASHIER_SESSION,
        entity_id=session.id,
        changes={
            "user_name": user.name,
            "old_values": old_values,
            "new_values": data.dict(exclude_unset=True)
        },
        description=f"Ajuste manual no caixa realizado por '{user.name}'"
    )

    db.commit()
    db.refresh(session)
    return session


@router.delete("/{id}")
def delete_session(
        request: Request,  # ✅ ADICIONAR
        id: int,
        db: GetDBDep,
        store: GetStoreDep,
        user: GetCurrentUserDep,
        audit: GetAuditLoggerDep  # ✅ ADICIONAR
):
    """
    ✅ Deleta uma sessão de caixa (ação administrativa crítica)
    """
    session = db.query(CashierSession).filter_by(id=id, store_id=store.id).first()
    if not session:
        raise HTTPException(
            status_code=404,
            detail="Sessão não encontrada ou não pertence à loja"
        )

    # Captura dados antes de deletar
    session_data = {
        "session_id": session.id,
        "store_name": store.name,
        "status": session.status,
        "opening_amount": float(session.opening_amount),
        "opened_at": session.opened_at.isoformat() if session.opened_at else None,
        "closed_at": session.closed_at.isoformat() if session.closed_at else None
    }

    # ✅ LOG DE DELEÇÃO
    audit.log(
        action=AuditAction.CLOSE_CASHIER,  # Usa CLOSE como ação genérica
        entity_type=AuditEntityType.CASHIER_SESSION,
        entity_id=session.id,
        changes={
            "deleted_by": user.name,
            "session_data": session_data
        },
        description=f"⚠️ Sessão de caixa DELETADA por '{user.name}' - ID: {session.id}"
    )

    db.delete(session)
    db.commit()

    return {"detail": "Sessão removida com sucesso"}