from pydantic import BaseModel, ConfigDict
from typing import Optional
from datetime import datetime

class StoreSettingsBase(BaseModel):
    is_delivery_active: Optional[bool] = True
    is_takeout_active: Optional[bool] = True
    is_table_service_active: Optional[bool] = True
    is_store_open: Optional[bool] = True
    auto_accept_orders: Optional[bool] = False
    auto_print_orders: Optional[bool] = False

    model_config = ConfigDict(from_attributes=True)  # 👈 permite aceitar ORM


