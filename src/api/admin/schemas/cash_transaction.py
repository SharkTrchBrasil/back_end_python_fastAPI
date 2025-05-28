from datetime import datetime
from pydantic import BaseModel

class CashierTransactionBase(BaseModel):
    cashier_session_id: int
    type: str  # ex: 'INFLOW', 'OUTFLOW', 'SALE', 'REFUND', etc.
    amount: float
    payment_method_id: int
    description: str | None = None
    order_id: int | None = None

class CashierTransactionCreate(CashierTransactionBase):
    pass

class CashierTransactionUpdate(BaseModel):
    type: str | None = None
    amount: float | None = None
    payment_method_id: int | None = None
    description: str | None = None
    order_id: int | None = None  # 👍 pode deixar aqui para updates também

class CashierTransactionOut(BaseModel):
    id: int
    cashier_session_id: int
    type: str
    amount: float
    payment_method_id: int
    description: str | None = None
    order_id: int | None = None
    created_at: datetime
    updated_at: datetime

    class Config:
        orm_mode = True  # ✅ importante para conversão automática via ORM
