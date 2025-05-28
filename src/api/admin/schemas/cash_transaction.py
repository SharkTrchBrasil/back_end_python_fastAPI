from pydantic import BaseModel


class CashierTransactionBase(BaseModel):
    cashier_session_id: int
    type: str  # entrada, saida, venda, sangria, etc.
    amount: float
    payment_method: str
    description: str | None = None
    order_id: int | None = None

class CashierTransactionCreate(CashierTransactionBase):
    pass

class CashierTransactionUpdate(BaseModel):
    type: str | None = None
    amount: float | None = None
    payment_method: str | None = None
    description: str | None = None
    order_id: int | None = None

class CashierTransactionOut(CashierTransactionBase):
    id: int

