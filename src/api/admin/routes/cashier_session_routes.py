from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from src.api.admin.schemas.cash_session import (
    CashierSessionUpdate,
    CashierSessionOut,
    CashierSessionCreate,
)
from src.core.database import GetDBDep
from src.core.dependencies import GetStoreDep
from src.core.models import CashierSession

router = APIRouter(prefix="/stores/{store_id}/cashier-sessions", tags=["Sessões de Caixa"])

@router.post("", response_model=CashierSessionOut)
def create_session(data: CashierSessionCreate, db: GetDBDep, store: GetStoreDep):
    # Verifica se já existe uma sessão aberta para a loja
    session_open = db.query(CashierSession).filter_by(store_id=store.id, status="open").first()
    if session_open:
        raise HTTPException(status_code=400, detail="Já existe uma sessão de caixa aberta para esta loja")

    session = CashierSession(**data.dict(), store_id=store.id, status="open")
    db.add(session)
    db.commit()
    db.refresh(session)
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
