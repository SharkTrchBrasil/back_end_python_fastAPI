# schemas/order/order.py
from datetime import datetime
from typing import Optional, Literal, List
from pydantic import Field, field_serializer, field_validator, ConfigDict

from src.core.utils.enums import OrderStatus
from ..base_schema import AppBaseModel
from .order_print_log import OrderPrintLogSchema
from .order_product import OrderProduct


class Order(AppBaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    sequential_id: int
    public_id: str
    store_id: int
    customer_id: int | None = None
    created_at: datetime
    updated_at: datetime
    scheduled_for: datetime | None = None
    customer_name: str | None = None
    customer_phone: str | None = None
    payment_method_name: str | None = None
    attendant_name: str | None = None
    observation: str | None = None
    street: str
    number: str | None = None
    complement: str | None = None
    neighborhood: str
    city: str
    order_type: str
    delivery_type: str
    consumption_type: str = "dine_in"
    is_scheduled: bool = False
    total_price: int
    subtotal_price: int | None = None
    discounted_total_price: int
    delivery_fee: int = 0
    change_amount: float | None = None
    discount_amount: int = 0
    discount_percentage: float | None = None
    discount_type: Literal['coupon', 'promotion', 'manual'] | None = None
    discount_reason: str | None = None
    payment_status: str
    order_status: OrderStatus
    payment_method_id: int | None = None
    needs_change: bool = False
    coupon_id: int | None = None
    coupon_code: str | None = None

    @field_serializer('scheduled_for', 'created_at', 'updated_at')
    def serialize_dates(self, value: datetime | None) -> str | None:
        return value.isoformat() if value else None

    @field_validator('order_status', mode='before')
    def validate_order_status(cls, v):
        if isinstance(v, OrderStatus):
            return v
        try:
            return OrderStatus(v.lower())
        except ValueError:
            raise ValueError(f"Status inválido. Opções válidas: {[e.value for e in OrderStatus]}")


class OrderDetails(Order):
    products: list[OrderProduct]
    customer_order_count: Optional[int] = 1
    print_logs: List[OrderPrintLogSchema] = []

    @field_validator('products', mode='before')
    def validate_products(cls, v):
        if not v:
            raise ValueError("A lista de produtos não pode estar vazia")
        return v

    model_config = ConfigDict(from_attributes=True)