# src/schemas/cash_movement.py (ou onde seus schemas de movimento estão)

from pydantic import BaseModel
from datetime import datetime
from typing import Optional

# Schema para a criação/entrada de movimento (o que o frontend envia)
class CashMovementCreate(BaseModel):
    amount: float
    type: str # 'in' ou 'out'
    note: Optional[str] = None

# Schema para a saída/retorno de movimento (o que o backend envia de volta)
class CashMovementOut(BaseModel):
    id: int
    register_id: int # Ou cash_register_id, dependendo do seu modelo
    amount: float
    type: str # 'in' ou 'out'
    note: Optional[str] = None
    created_at: datetime
    updated_at: datetime # Se você tiver timestamps para movimentos

    class Config:
        from_attributes = True # ou orm_mode = True para Pydantic v1