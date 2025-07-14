from typing import Optional

from pydantic import BaseModel


class OrderPartialPaymentBase(BaseModel):
    amount: int
    payment_method_id: Optional[int] = None
    received_by: Optional[str] = None


class OrderPartialPaymentCreate(OrderPartialPaymentBase):
    order_id: int


class OrderPartialPaymentOut(OrderPartialPaymentBase):
    id: int
    order_id: int

    class Config:
        orm_mode = True
