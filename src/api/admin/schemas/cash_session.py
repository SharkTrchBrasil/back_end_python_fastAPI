from datetime import datetime

from pydantic import BaseModel


class CashierSessionBase(BaseModel):
    cash_register_id: int
    user_opened_id: int
    opening_amount: float
    notes: str | None = None

class CashierSessionCreate(CashierSessionBase):
    pass

class CashierSessionUpdate(BaseModel):
    user_closed_id: int | None = None
    closed_at: datetime | None = None
    cash_added: float | None = None
    cash_removed: float | None = None
    total_sales: float | None = None
    total_received: float | None = None
    closing_amount: float | None = None
    gross_profit: float | None = None
    cash_difference: float | None = None
    status: str | None = None
    notes: str | None = None

class CashierSessionOut(CashierSessionBase):
    id: int
    user_closed_id: int | None
    opened_at: datetime
    closed_at: datetime | None
    cash_added: float
    cash_removed: float
    total_sales: float
    total_received: float
    closing_amount: float | None
    gross_profit: float
    cash_difference: float
    status: str
    created_at: datetime
    updated_at: datetime

    class Config:
        orm_mode = True
