from typing import Optional

from pydantic import BaseModel


class CommandBase(BaseModel):
    customer_name: Optional[str] = None


class CommandCreate(CommandBase):
    store_id: int
    table_id: Optional[int] = None


class CommandUpdate(BaseModel):
    table_id: Optional[int] = None
    customer_name: Optional[str] = None
    is_active: Optional[bool] = None


class CommandOut(CommandBase):
    id: int
    store_id: int
    table_id: Optional[int]
    is_active: bool

    class Config:
        from_attributes = True

