from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class TableBase(BaseModel):
    name: str


class TableCreate(TableBase):
    store_id: int


class TableUpdate(BaseModel):
    name: Optional[str] = None
    is_open: Optional[bool] = None
    closed_at: Optional[datetime] = None


class TableOut(TableBase):
    id: int
    store_id: int
    is_open: bool
    opened_at: datetime
    closed_at: Optional[datetime]

    class Config:
        from_attributes = True

