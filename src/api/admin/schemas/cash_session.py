from datetime import datetime
from pydantic import BaseModel


class CashierSessionBase(BaseModel):
    user_opened_id: int


class CashierSessionCreate(BaseModel):
    opening_amount: float = 0.0

class CashierSessionUpdate(BaseModel):
    user_closed_id: int | None = None
    closed_at: datetime | None = None
    cash_difference: float | None = None
    expected_amount: float  # quanto o sistema esperava
    informed_amount: float  # quanto o operador contou
    status: str | None = None
    cash_added: float | None = None
    cash_removed: float | None = None


class CashierSessionOut(CashierSessionBase):
    id: int
    user_closed_id: int | None
    opened_at: datetime
    closed_at: datetime | None
    cash_added: float | None = None
    cash_removed: float | None = None
    cash_difference: float | None = None
    status: str
    opening_amount: float = 0.0


    class Config:
        orm_mode = True
