from pydantic import BaseModel
from typing import Optional
from datetime import datetime

class StoreSettingsBase(BaseModel):
    is_delivery_active: Optional[bool] = True
    is_takeout_active: Optional[bool] = True
    is_table_service_active: Optional[bool] = True
    is_store_open: Optional[bool] = True
    auto_accept_orders: Optional[bool] = False
    auto_print_orders: Optional[bool] = False

class StoreSettingsCreate(StoreSettingsBase):
    pass

class StoreSettingsUpdate(StoreSettingsBase):
    pass

class StoreSettingsOut(StoreSettingsBase):
    store_id: int
    created_at: Optional[datetime]
    updated_at: Optional[datetime]

    class Config:
        orm_mode = True
