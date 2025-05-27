from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, joinedload

from src.api.admin.schemas.cash_session import (
    CashierSessionUpdate,
    CashierSessionOut,
    CashierSessionCreate,
)
from src.core.database import GetDBDep
from src.core.dependencies import GetStoreDep
from src.core.models import CashierSession, CashRegister

router = APIRouter(prefix="/stores/{store_id}/cashier-sessions", tags=["Sessões de Caixa"])

@router.post("", response_model=CashierSessionOut)
def create_session(data: CashierSessionCreate, db: GetDBDep, store: GetStoreDep):
    # Verifica se o caixa pertence à loja
    register = db.query(CashRegister).filter_by(id=data.cash_register_id, store_id=store.id).first()
    if not register:
        raise HTTPException(status_code=404, detail="Caixa não encontrado ou não pertence à loja")

    session = CashierSession(**data.dict())
    db.add(session)
    db.commit()
    db.refresh(session)
    return session

@router.get("/{id}", response_model=CashierSessionOut)
def get_session(id: int, db: GetDBDep, store: GetStoreDep):
    session = (
        db.query(CashierSession)
        .options(joinedload(CashierSession.cash_register))
        .filter(CashierSession.id == id)
        .first()
    )
    if not session or session.cash_register.store_id != store.id:
        raise HTTPException(status_code=404, detail="Sessão não encontrada ou não pertence à loja")
    return session

@router.get("", response_model=list[CashierSessionOut])
def list_sessions(db: GetDBDep, store: GetStoreDep):
    return (
        db.query(CashierSession)
        .join(CashierSession.cash_register)
        .filter(CashRegister.store_id == store.id)
        .all()
    )

@router.put("/{id}", response_model=CashierSessionOut)
def update_session(id: int, data: CashierSessionUpdate, db: GetDBDep, store: GetStoreDep):
    session = (
        db.query(CashierSession)
        .options(joinedload(CashierSession.cash_register))
        .filter(CashierSession.id == id)
        .first()
    )
    if not session or session.cash_register.store_id != store.id:
        raise HTTPException(status_code=404, detail="Sessão não encontrada ou não pertence à loja")

    for key, value in data.dict(exclude_unset=True).items():
        setattr(session, key, value)
    db.commit()
    db.refresh(session)
    return session

@router.delete("/{id}")
def delete_session(id: int, db: GetDBDep, store: GetStoreDep):
    session = (
        db.query(CashierSession)
        .options(joinedload(CashierSession.cash_register))
        .filter(CashierSession.id == id)
        .first()
    )
    if not session or session.cash_register.store_id != store.id:
        raise HTTPException(status_code=404, detail="Sessão não encontrada ou não pertence à loja")

    db.delete(session)
    db.commit()
    return {"detail": "Sessão removida com sucesso"}
