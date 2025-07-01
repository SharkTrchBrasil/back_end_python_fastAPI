from datetime import datetime

from pydantic import BaseModel, ConfigDict


class OrderProductVariantOption(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    quantity: int


class OrderProductVariant(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    options: list[OrderProductVariantOption]


class OrderProductTicket(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    ticket_code: str
    status: int


class OrderProduct(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    quantity: int
    variants: list[OrderProductVariant]
    tickets: list[OrderProductTicket]
    price: int


class Order(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    phone: str
    name: str
    total_price: int
    discounted_total_price: int
    totem_name: str | None = None
    charge_status: str | None = None
    created_at: datetime


class OrderDetails(Order):
    products: list[OrderProduct]