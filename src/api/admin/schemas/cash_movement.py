from pydantic import BaseModel, Field
from decimal import Decimal
from typing import Optional

class CashMovementCreate(BaseModel):
    type: str = Field(..., pattern="^(in|out)$", description="Tipo de movimento: 'in' para entrada, 'out' para saída")
    amount: Decimal = Field(..., gt=0, description="Valor do movimento em dinheiro")
    note: Optional[str] = Field(None, description="Observação opcional sobre o movimento")
