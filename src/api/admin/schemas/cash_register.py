from pydantic import BaseModel
from datetime import datetime

class CashRegisterBase(BaseModel):

    number: int
    name: str
    is_active: bool = True

class CashRegisterCreate(CashRegisterBase):
    pass

class CashRegisterUpdate(BaseModel):
    number: int | None = None
    name: str | None = None
    is_active: bool | None = None

class CashRegisterOut(CashRegisterBase):
    id: int
    created_at: datetime
    updated_at: datetime


