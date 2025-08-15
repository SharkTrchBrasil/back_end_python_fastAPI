from pydantic import BaseModel, Field



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

    activation: StorePaymentMethodActivationOut | None = None

    class Config:
        from_attributes = True



class PaymentMethodCategoryOut(BaseModel):
    name: str
    methods: list[PlatformPaymentMethodOut] = []  # Contém uma lista de métodos

    class Config:
        from_attributes = True



class PaymentMethodGroupOut(BaseModel):
    name: str
    categories: list[PaymentMethodCategoryOut] = []  # Contém uma lista de categorias

    class Config:
        from_attributes = True