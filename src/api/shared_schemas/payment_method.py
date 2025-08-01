from pydantic import BaseModel


# --- Nível 1: A Configuração da Loja (O que foi ativado) ---
# Representa a tabela 'store_payment_method_activations'
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


# --- Nível 2: A Opção Final (O Método de Pagamento) ---
# Representa a tabela 'platform_payment_methods'
class PlatformPaymentMethodOut(BaseModel):
    id: int
    name: str
    icon_key: str | None = None

    # Aninha a configuração específica da loja dentro do método
    activation: StorePaymentMethodActivationOut | None = None

    class Config:
        from_attributes = True


# --- Nível 3: A Categoria ---
# Representa a tabela 'payment_method_categories'
class PaymentMethodCategoryOut(BaseModel):
    name: str
    methods: list[PlatformPaymentMethodOut] = []  # Contém uma lista de métodos

    class Config:
        from_attributes = True


# --- Nível 4: O Grupo Principal ---
# Representa a tabela 'payment_method_groups'
class PaymentMethodGroupOut(BaseModel):
    name: str
    categories: list[PaymentMethodCategoryOut] = []  # Contém uma lista de categorias

    class Config:
        from_attributes = True