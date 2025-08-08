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
    due_date: date
    payment_date: date | None = None
    barcode: str | None = None
    status: PayableStatus = PayableStatus.pending




class StorePayableCreate(StorePayableBase):
    pass  # Usa os mesmos campos do base



class StorePayableUpdate(BaseModel):
    title: str | None = None
    description: str | None = None

    amount: float | None = None

    due_date: date | None = None
    payment_date: date | None = None

    barcode: str | None = None
    status: PayableStatus | None = None






class StorePayableOut(StorePayableBase):
    id: int
    store_id: int

    class Config:
        orm_mode = True
