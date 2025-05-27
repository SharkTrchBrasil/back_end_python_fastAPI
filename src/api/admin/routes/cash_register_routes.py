

from fastapi import APIRouter, HTTPException

from sqlalchemy import func
from decimal import Decimal

from src.api.admin.schemas.cash_register import CashRegisterOut
from src.core.database import GetDBDep

from src.core.models import CashRegister, CashMovement




router = APIRouter(prefix="/{store_id}/cash-register", tags=["Cash Register"])

# Rota para obter o caixa aberto
@router.get("/open", response_model=CashRegisterOut)
def get_open_cash_register(store_id: int, db: GetDBDep):
    cash_register = db.query(CashRegister).filter(
        CashRegister.store_id == store_id,
        CashRegister.closed_at.is_(None)
    ).first()

    if not cash_register:
        raise HTTPException(status_code=404, detail="Nenhum caixa aberto para esta loja.")

    # --- CALCULAR TOTAIS DE ENTRADA E SAÍDA ---
    # Soma dos movimentos de entrada
    total_in_query = db.query(func.sum(CashMovement.amount)).filter(
        CashMovement.register_id == cash_register.id,
        CashMovement.type == 'in'
    ).scalar() or Decimal('0.00') if isinstance(cash_register.initial_balance, Decimal) else 0.0

    # Soma dos movimentos de saída
    total_out_query = db.query(func.sum(CashMovement.amount)).filter(
        CashMovement.register_id == cash_register.id,
        CashMovement.type == 'out'
    ).scalar() or Decimal('0.00') if isinstance(cash_register.initial_balance, Decimal) else 0.0

    # Criar uma instância de CashRegisterOut com os totais
    # O Pydantic irá lidar com a serialização dos campos diretamente do objeto ORM
    # mas você precisa passar os campos calculados separadamente.
    response_data = CashRegisterOut(
        id=cash_register.id,
        store_id=cash_register.store_id,
        opened_at=cash_register.opened_at,
        closed_at=cash_register.closed_at,
        initial_balance=cash_register.initial_balance,
        current_balance=cash_register.current_balance,
        is_active=cash_register.is_active,
        created_at=cash_register.created_at,
        updated_at=cash_register.updated_at,
        total_in=float(total_in_query) if isinstance(total_in_query, Decimal) else total_in_query, # Converte para float se for Decimal
        total_out=float(total_out_query) if isinstance(total_out_query, Decimal) else total_out_query, # Converte para float se for Decimal
    )

    return response_data # Retorna o objeto CashRegisterOut preenchido