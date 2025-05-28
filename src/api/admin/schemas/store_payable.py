from pydantic import BaseModel
from datetime import date
from enum import Enum

class PayableStatus(str, Enum):
    pending = "pending"
    paid = "paid"
    overdue = "overdue"
    cancelled = "cancelled"

class StorePayableBase(BaseModel):
    title: str
    description: str | None = None

    amount: float
    discount: float = 0.0
    addition: float = 0.0

    due_date: date
    payment_date: date | None = None

    barcode: str | None = None

    status: PayableStatus = PayableStatus.pending

    is_recurring: bool = False
    notes: str | None = None





class StorePayableCreate(StorePayableBase):
    pass  # Usa os mesmos campos do base



class StorePayableUpdate(BaseModel):
    title: str | None = None
    description: str | None = None

    amount: float | None = None
    discount: float | None = None
    addition: float | None = None

    due_date: date | None = None
    payment_date: date | None = None

    barcode: str | None = None
    status: PayableStatus | None = None

    is_recurring: bool | None = None
    notes: str | None = None





class StorePayableOut(StorePayableBase):
    id: int
    store_id: int

    class Config:
        orm_mode = True
