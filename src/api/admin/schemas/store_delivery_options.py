from pydantic import BaseModel
from typing import Optional
from datetime import datetime

class StoreDeliveryOptionBase(BaseModel):
    type: str  # delivery, pickup, table
    title: str
    enabled: Optional[bool] = True

    estimated_min: Optional[int] = None
    estimated_max: Optional[int] = None

    delivery_fee: Optional[float] = None
    min_order_value: Optional[float] = None

    instructions: Optional[str] = None

class StoreDeliveryOptionCreate(StoreDeliveryOptionBase):
    pass

class StoreDeliveryOptionUpdate(StoreDeliveryOptionBase):
    pass

class StoreDeliveryOption(StoreDeliveryOptionBase):
    id: int
    store_id: int
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        orm_mode = True
