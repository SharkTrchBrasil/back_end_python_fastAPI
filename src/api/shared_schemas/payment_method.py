from datetime import datetime
from typing import Optional

from pydantic import BaseModel, computed_field, Field


class StorePaymentMethods(BaseModel):
    id: int
    payment_type: str = Field(..., max_length=20)
    custom_name: str
    custom_icon: str = None
    is_active: bool = True
    active_on_delivery: bool = True
    active_on_pickup: bool = True
    active_on_counter: bool = True
    tax_rate: float = 0.0
    pix_key: Optional[str]


    model_config = {
        "from_attributes": True
    }
