# schemas/order/order_input.py
from typing import Optional
from pydantic import ConfigDict

from ..base_schema import AppBaseModel


class CreateOrderInput(AppBaseModel):
    payment_method_id: int
    delivery_type: str
    observation: Optional[str] = None
    needs_change: Optional[bool] = False
    change_for: Optional[float] = None
    address_id: Optional[int] = None
    delivery_fee: Optional[int] = None

    model_config = ConfigDict(from_attributes=True)