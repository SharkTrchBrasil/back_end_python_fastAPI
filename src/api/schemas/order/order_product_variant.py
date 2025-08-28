# schemas/order/order_product_variant.py
from typing import List
from pydantic import ConfigDict

from ..base_schema import AppBaseModel
from .order_variant_option import OrderVariantOption


class OrderProductVariant(AppBaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    variant_id: int | None = None
    options: list[OrderVariantOption]