from pydantic import BaseModel, Field, computed_field


class StorePaymentMethodActivationOut(BaseModel):
    id: int
    is_active: bool
    fee_percentage: float = 0.0
    details: dict | None = None
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


# ✅ ================== CORREÇÃO AQUI ==================
# O grupo agora contém a lista de métodos diretamente.
class PaymentMethodGroupOut(BaseModel):
    name: str
    title: str | None = None
    description: str | None = None

    # A lista de métodos agora faz parte do grupo.
    methods: list[PlatformPaymentMethodOut] = []

    class Config:
        from_attributes = True