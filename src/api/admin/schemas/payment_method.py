from datetime import datetime
from typing import Optional

from pydantic import BaseModel, computed_field, Field


class StorePaymentMethods(BaseModel):
    id: int
    store_id: int

    # 'Cash', 'Card', 'Check', 'Pix', 'Other'
    payment_type: str = Field(..., max_length=20)

    custom_name: str
    custom_icon: str = None

    # check‑boxes / flags
    change_back: bool = False
    credit_in_account: bool = False
    is_active: bool = True

    # canal de venda
    active_on_delivery: bool = True
    active_on_pickup: bool = True
    active_on_counter: bool = True

    # financeiro
    tax_rate: float = 0.0
    days_to_receive: int = 0
    has_fee: bool = False

    # Pix
    pix_key: Optional[str]
    pix_key_active: bool = False

    # timestamps
    created_at: datetime | None = None
    updated_at: datetime | None = None

