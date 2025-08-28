# schemas/order/order_variant_option.py
from pydantic import ConfigDict

from ..base_schema import AppBaseModel


class OrderVariantOption(AppBaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    quantity: int
    price: int
    variant_option_id: int | None = None