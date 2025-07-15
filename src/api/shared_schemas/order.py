from datetime import datetime
from typing import Optional, Literal
from pydantic import BaseModel, ConfigDict, Field, field_serializer
from pydantic import field_validator
from enum import Enum


class OrderStatus(str, Enum):
    PENDING = 'pending'
    PREPARING = 'preparing'
    READY = 'ready'
    ON_ROUTE = 'on_route'
    DELIVERED = 'delivered'
    CANCELED = 'canceled'


class OrderVariantOption(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    quantity: int
    price: int
    variant_option_id: int | None = None


class OrderProductVariant(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    variant_id: int | None = None
    options: list[OrderVariantOption]


class OrderProduct(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    product_id: int | None = None
    store_id: int | None = None
    name: str
    note: str | None = None
    quantity: int
    variants: list[OrderProductVariant]
    price: int
    # Novos campos
    image_url: str | None = None
    original_price: int = Field(..., description="Preço antes de descontos")
    discount_amount: int = Field(0, description="Valor do desconto neste item")
    discount_percentage: float | None = Field(
        None,
        description="Porcentagem de desconto se aplicável"
    )
    applied_discounts: dict | None = Field(
        None,
        description="Detalhes dos descontos aplicados"
    )


class Order(BaseModel):
    id: int
    sequential_id: int
    public_id: str
    store_id: int
    customer_id: int | None = None
    discounted_total_price: int
    created_at: datetime
    updated_at: datetime
    scheduled_for: datetime | None = None
    observation: str | None = None

    # Campos desnormalizados
    customer_name: str | None = None
    customer_phone: str | None = None
    payment_method_name: str | None = None

    # Endereço
    street: str
    number: str | None = None
    complement: str | None = None
    neighborhood: str
    city: str

    # Status
    is_scheduled: bool = False
    consumption_type: str = "dine_in"
    attendant_name: str | None = None
    order_type: str
    delivery_type: str
    total_price: int
    payment_status: str
    order_status: OrderStatus
    payment_method_id: int | None = None
    needs_change: bool = False
    change_amount: float | None = None

    # Novos campos
    discount_amount: int = Field(0, description="Valor total do desconto em centavos")
    discount_percentage: float | None = Field(
        None,
        description="Porcentagem de desconto se aplicável"
    )
    discount_type: Literal['coupon', 'promotion', 'manual'] | None = Field(
        None,
        description="Tipo de desconto aplicado"
    )
    discount_reason: str | None = Field(
        None,
        description="Descrição/motivo do desconto"
    )
    subtotal_price: int = Field(
        ...,
        description="Valor total antes de descontos e taxas"
    )
    coupon_id: int | None = Field(
        None,
        description="ID do cupom aplicado, se houver"
    )
    coupon_code: str | None = Field(
        None,
        description="Código do cupom aplicado"
    )
    delivery_fee: int | None = Field(
        None,
        description="Taxa de entrega em centavos"
    )

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

    model_config = ConfigDict(from_attributes=True)


class OrderDetails(Order):
    products: list[OrderProduct]

    @field_validator('products', mode='before')
    def validate_products(cls, v):
        if not v:
            raise ValueError("A lista de produtos não pode estar vazia")
        return v

    model_config = ConfigDict(from_attributes=True)





