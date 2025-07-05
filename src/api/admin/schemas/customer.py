from pydantic import BaseModel
from datetime import datetime
from typing import Optional

class StoreCustomerOut(BaseModel):
    customer_id: int
    name: str
    phone: Optional[str]
    email: Optional[str] = None
    total_orders: int
    total_spent: int
    last_order_at: Optional[datetime]

    class Config:
        orm_mode = True
