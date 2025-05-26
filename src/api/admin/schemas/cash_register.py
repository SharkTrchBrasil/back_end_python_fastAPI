from pydantic import BaseModel
from datetime import datetime

class CashRegisterBase(BaseModel):
    store_id: int
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

    class Config:
        orm_mode = True
