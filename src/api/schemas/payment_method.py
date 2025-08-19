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

    activation: StorePaymentMethodActivationOut | None = None


    # ✅ Adicione um campo computado
    @computed_field
    @property
    def requires_manual_setup(self) -> bool:
        # A lógica de negócio fica centralizada aqui no backend
        CONFIGURABLE_TYPES = {'CASH', 'PIX', 'POS_MACHINE'}
        return self.method_type in CONFIGURABLE_TYPES

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