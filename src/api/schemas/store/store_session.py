# schemas/store/store_session.py
from datetime import datetime

from pydantic import ConfigDict

from ..base_schema import AppBaseModel


class StoreSessionBase(AppBaseModel):
    store_id: int
    client_type: str
    sid: str


class StoreSessionCreate(StoreSessionBase):
    pass


class StoreSessionRead(StoreSessionBase):
    id: int
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)