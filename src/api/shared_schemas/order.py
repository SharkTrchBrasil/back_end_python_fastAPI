from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, field_serializer


class OrderVariantOption(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    quantity: int


class OrderProductVariant(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    options: list[OrderVariantOption]

#
# class OrderProductTickets(BaseModel):
#     model_config = ConfigDict(from_attributes=True)
#
#     id: int
#     ticket_code: str
#     status: int


class OrderProduct(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    note: str | None = None
    quantity: int
    variants: list[OrderProductVariant]
   # tickets: list[OrderProductTickets]
    price: int



# class Charge(BaseModel):
#     status: str
#     amount: float
#     copy_key: str
#     expires_at: datetime
#
#     model_config = ConfigDict(from_attributes=True)
#

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
    is_scheduled: bool | None = False
    consumption_type: str = "dine_in"
    attendant_name: str | None = None
    order_type: str
    delivery_type: str
    total_price: int
    payment_status: str
    order_status: str
    payment_method_id: int
    needs_change: bool = False
    change_amount: float | None = None



    @field_serializer('scheduled_for', 'created_at', 'updated_at')
    def serialize_dates(self, value: datetime | None) -> str | None:
        return value.isoformat() if value else None

    model_config = ConfigDict(from_attributes=True)


class OrderDetails(Order):
    products: list[OrderProduct]
    model_config = ConfigDict(from_attributes=True)

