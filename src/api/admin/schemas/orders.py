from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, condecimal

class OrderBase(BaseModel):
    store_id: int
    register_id: Optional[int]
    status: str = "pending"
    total: condecimal(max_digits=10, decimal_places=2)
    payment_method_id: int
    note: Optional[str] = None

class OrderCreate(OrderBase):
    pass

class OrderUpdate(BaseModel):
    status: Optional[str]
    total: Optional[condecimal(max_digits=10, decimal_places=2)]
    payment_method_id: Optional[int]
    note: Optional[str]

class OrderInDBBase(OrderBase):
    id: int
    created_at: datetime

    class Config:
        orm_mode = True

class Order(OrderInDBBase):
    pass

# Se quiser detalhar relacionamento, pode fazer assim:
class CashierTransactionSchema(BaseModel):
    # Defina aqui o que precisar dos transactions
    id: int
    type: str
    amount: condecimal(max_digits=10, decimal_places=2)
    payment_method: str  # ou melhor referenciar o schema da forma de pagamento, se desejar

    class Config:
        orm_mode = True

class OrderWithTransactions(Order):
    transactions: List[CashierTransactionSchema] = []
