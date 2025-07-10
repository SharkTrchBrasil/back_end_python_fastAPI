from pydantic import BaseModel
from datetime import datetime

class StoreSessionBase(BaseModel):
    store_id: int
    client_type: str  # 'admin' ou 'totem'
    sid: str

class StoreSessionCreate(StoreSessionBase):
    pass

class StoreSessionRead(StoreSessionBase):
    id: int
    created_at: datetime

    class Config:
        orm_mode = True
