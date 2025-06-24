from datetime import datetime

from pydantic import BaseModel, ConfigDict


class Charge(BaseModel):
    status: str
    amount: float
    copy_key: str
    expires_at: datetime

    model_config = ConfigDict(from_attributes=True)


class Order(BaseModel):
    id: int
    sequential_id: int
    public_id: str
    store_id: int
    customer_id: int | None = None
    customer_address_id: int | None = None
    attendant_name: str | None = None
    order_type: str
    delivery_type: str
    total_price: int
    payment_status: str
    order_status: str
    charge: Charge | None  # modelo aninhado
    totem_id: int | None = None
    needs_change: bool = False
    change_amount: float | None = None
    payment_method_id: int


    model_config = ConfigDict(from_attributes=True)