from pydantic import BaseModel, Field, computed_field


class StorePaymentMethodActivationOut(BaseModel):
    id: int
    is_active: bool
    fee_percentage: float = 0.0
    details: dict | None = None  # Armazena a chave Pix, etc.
    is_for_delivery: bool
    is_for_pickup: bool
    is_for_in_store: bool

    class Config:
        from_attributes = True



class PlatformPaymentMethodOut(BaseModel):
    id: int
    name: str
    icon_key: str | None = None
    method_type: str
    requires_details: bool
    activation: StorePaymentMethodActivationOut | None = None


    class Config:
        from_attributes = True


# ✅ SCHEMA DE GRUPO ATUALIZADO
class PaymentMethodGroupOut(BaseModel):
    name: str
    title: str | None = None
    description: str | None = None

    # ✅ AGORA ELE TEM UMA LISTA DE MÉTODOS DIRETAMENTE
    methods: list[PlatformPaymentMethodOut] = []

    class Config:
        from_attributes = True