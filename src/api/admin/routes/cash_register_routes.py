from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from src.api.admin.schemas.cash_register import CashRegisterOut, CashRegisterCreate, CashRegisterUpdate
from src.core.database import GetDBDep
from src.core.dependencies import GetStoreDep
from src.core.models import CashRegister

router = APIRouter(prefix="/stores/{store_id}/cash_registers", tags=["Caixas"])

@router.post("", response_model=CashRegisterOut)
def create_cash_register(data: CashRegisterCreate, db: GetDBDep, store: GetStoreDep):
    register = CashRegister(**data.model_dump(), store_id=store.id)
    db.add(register)
    db.commit()
    db.refresh(register)
    return register

@router.get("/{id}", response_model=CashRegisterOut)
def get_cash_register(id: int, db: GetDBDep, store: GetStoreDep):
    register = db.query(CashRegister).filter_by(id=id, store_id=store.id).first()
    if not register:
        raise HTTPException(status_code=404, detail="Caixa não encontrado")
    return register

@router.get("", response_model=list[CashRegisterOut])
def list_cash_registers(db: GetDBDep, store: GetStoreDep):
    return db.query(CashRegister).filter_by(store_id=store.id).all()

@router.put("/{id}", response_model=CashRegisterOut)
def update_cash_register(id: int, data: CashRegisterUpdate, db: GetDBDep, store: GetStoreDep):
    register = db.query(CashRegister).filter_by(id=id, store_id=store.id).first()
    if not register:
        raise HTTPException(status_code=404, detail="Caixa não encontrado")
    for key, value in data.dict(exclude_unset=True).items():
        setattr(register, key, value)
    db.commit()
    db.refresh(register)
    return register

@router.delete("/{id}")
def delete_cash_register(id: int, db: GetDBDep, store: GetStoreDep):
    register = db.query(CashRegister).filter_by(id=id, store_id=store.id).first()
    if not register:
        raise HTTPException(status_code=404, detail="Caixa não encontrado")
    db.delete(register)
    db.commit()
    return {"detail": "Caixa removido com sucesso"}
