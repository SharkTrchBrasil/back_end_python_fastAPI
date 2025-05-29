from datetime import datetime
from pydantic import BaseModel


class CashierSessionBase(BaseModel):
    user_opened_id: int
    notes: str | None = None



class CashierSessionCreate(BaseModel):
    opening_amount: float = 0.0
    notes: str | None = None
    payment_method_id: int  # ✅ adicionar esse campo

class CashierSessionUpdate(BaseModel):
    user_closed_id: int | None = None
    closed_at: datetime | None = None
    total_sales: float | None = None
    total_received: float | None = None
    closing_amount: float | None = None
    gross_profit: float | None = None
    cash_difference: float | None = None
    status: str | None = None
    notes: str | None = None
    cash_added: float | None = None
    cash_removed: float | None = None


class CashierSessionOut(CashierSessionBase):
    id: int
    user_closed_id: int | None
    opened_at: datetime
    closed_at: datetime | None
    cash_added: float | None = None
    cash_removed: float | None = None
    total_sales: float | None = None
    total_received: float | None = None
    closing_amount: float | None = None
    gross_profit: float | None = None
    cash_difference: float | None = None
    status: str
    opening_amount: float = 0.0
    total_cash_sales: float | None = 0.0

    class Config:
        orm_mode = True
