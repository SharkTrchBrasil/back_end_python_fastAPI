from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from datetime import datetime

from src.api.admin.schemas.cash_register import (
    CashRegisterOut,
    CashRegisterCreate,
    CashRegisterCreateUpdateBase,
)
from src.api.admin.schemas.cash_movement import CashMovementCreate
from src.core.database import GetDBDep
from src.core.dependencies import GetStoreDep
from src.core.models import CashRegister, CashMovement

router = APIRouter(prefix="/stores/{store_id}/cash-register", tags=["Caixas"])


# 🔄 Buscar caixa aberto
@router.get("/open", response_model=CashRegisterOut)
def get_open_cash_register(db: GetDBDep, store: GetStoreDep):
    register = (
        db.query(CashRegister)
        .filter_by(store_id=store.id, closed_at=None)
        .order_by(CashRegister.id.desc())
        .first()
    )
    if not register:
        raise HTTPException(status_code=404, detail="Nenhum caixa aberto")
    return register


# 📦 Abrir o caixa
@router.post("/open", response_model=CashRegisterOut)
def open_cash_register(data: CashRegisterCreate, db: GetDBDep, store: GetStoreDep):
    existing_open = (
        db.query(CashRegister)
        .filter_by(store_id=store.id, closed_at=None)
        .first()
    )
    if existing_open:
        raise HTTPException(status_code=400, detail="Já existe um caixa aberto")

    register = CashRegister(
        store_id=store.id,
        opened_at=datetime.utcnow(),
        initial_balance=data.initial_balance,
        current_balance=data.initial_balance,
        number=data.number,  # ADICIONAR
        name=data.name,  # ADICIONAR
        is_active=data.is_active,  # Opcional
    )
    db.add(register)
    db.commit()
    db.refresh(register)
    return register


# 🧾 Fechar o caixa
@router.post("/{id}/close", response_model=CashRegisterOut)
def close_cash_register(id: int, db: GetDBDep, store: GetStoreDep):
    register = (
        db.query(CashRegister)
        .filter_by(id=id, store_id=store.id, closed_at=None)
        .first()
    )
    if not register:
        raise HTTPException(status_code=404, detail="Caixa não encontrado ou já fechado")

    register.closed_at = datetime.utcnow()
    db.commit()
    return {"detail": "Caixa fechado com sucesso"}


# ➕➖ Adicionar movimentação ao caixa
@router.post("/{id}/movement", response_model=CashRegisterOut)
def add_cash_movement(
        id: int,
        data: CashMovementCreate,
        db: GetDBDep,
        store: GetStoreDep
):
    register = db.query(CashRegister).filter_by(id=id, store_id=store.id).first()
    if not register or register.closed_at is not None:
        raise HTTPException(status_code=404, detail="Caixa não encontrado ou já fechado")

    if data.type == "out" and register.current_balance < data.amount:
        raise HTTPException(status_code=400, detail="Saldo insuficiente para retirada")

    movement = CashMovement(
        register_id=id,
        store_id=store.id,
        type=data.type,
        amount=data.amount,
        note=data.note,
        created_at=datetime.utcnow(),
    )

    # Atualiza saldo atual
    if data.type == "in":
        register.current_balance += data.amount
    elif data.type == "out":
        register.current_balance -= data.amount

    db.add(movement)
    db.commit()
    return {"detail": "Movimento registrado com sucesso"}
