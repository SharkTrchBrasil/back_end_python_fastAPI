# schemas/order/partial_payment.py
from datetime import datetime
from typing import Optional
from pydantic import ConfigDict

from ..base_schema import AppBaseModel


class PartialPaymentCreateSchema(AppBaseModel):
    store_payment_method_activation_id: int
    amount: int
    received_by: Optional[str] = None
    transaction_id: Optional[str] = None
    notes: Optional[str] = None


class PartialPaymentResponseSchema(AppBaseModel):
    id: int
    amount: int
    payment_method_name: str
    received_by: Optional[str] = None
    transaction_id: Optional[str] = None
    notes: Optional[str] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)