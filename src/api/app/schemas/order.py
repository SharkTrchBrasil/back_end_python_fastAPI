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



    # ✅ Novos campos desnormalizados
    customer_name: str | None = None           # 👈 Nome do cliente no momento do pedido
    customer_phone: str | None = None          # 👈 Telefone do cliente
    payment_method_name: str | None = None     # 👈 Ex: "Pix via MercadoPago"

    # ✅ Dados do endereço fixos no pedido
    street: str
    number: str | None = None
    complement: str | None = None
    neighborhood: str
    city: str




    attendant_name: str | None = None
    order_type: str
    delivery_type: str
    total_price: int
    payment_status: str
    order_status: str
    charge: Charge | None
    totem_id: int | None = None
    needs_change: bool = False
    change_amount: float | None = None
    payment_method_id: int

    model_config = ConfigDict(from_attributes=True)
