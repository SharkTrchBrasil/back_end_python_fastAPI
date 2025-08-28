# schemas/order/order_product.py
from typing import List
from pydantic import Field, ConfigDict

from ..base_schema import AppBaseModel
from .order_product_variant import OrderProductVariant


class OrderProduct(AppBaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    product_id: int | None = None
    store_id: int | None = None
    name: str
    note: str | None = None
    quantity: int
    variants: list[OrderProductVariant]
    price: int
    image_url: str | None = None
    original_price: int = Field(..., description="Preço antes de descontos")
    discount_amount: int = Field(0, description="Valor do desconto neste item")
    discount_percentage: float | None = Field(None, description="Porcentagem de desconto se aplicável")
    applied_discounts: dict | None = Field(None, description="Detalhes dos descontos aplicados")