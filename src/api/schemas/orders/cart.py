# Em: app/schemas/cart.py
from pydantic import BaseModel, Field
from typing import Optional, List

from src.api.schemas.products.product import ProductOut


# =====================================================================================
# SEÇÃO 1: SCHEMAS DE SAÍDA (O que o backend envia para o Flutter)
# =====================================================================================

# --- Schemas aninhados primeiro ---

class CartItemVariantOptionSchema(BaseModel):
    """Representa uma opção de complemento selecionada no carrinho."""
    variant_option_id: int
    quantity: int
    name: str  # ✅ OBRIGATÓRIO: Para a UI exibir o nome da opção (ex: "Bacon")
    price: int # ✅ OBRIGATÓRIO: Para a UI exibir o preço da opção (ex: 300 centavos)

    class ConfigDict:
        from_attributes = True

class CartItemVariantSchema(BaseModel):
    """Representa um grupo de complementos (ex: "Adicionais") no carrinho."""
    variant_id: int
    name: str  # ✅ OBRIGATÓRIO: Para a UI exibir o nome do grupo (ex: "Adicionais")
    options: List[CartItemVariantOptionSchema]

    class ConfigDict:
        from_attributes = True



class CartItemSchema(BaseModel):
    """Representa um item completo no carrinho."""
    id: int
    product: ProductOut
    quantity: int
    note: Optional[str] = None
    variants: List[CartItemVariantSchema]

    # Campos calculados em tempo real no backend
    unit_price: int
    total_price: int

    class ConfigDict:
        from_attributes = True

class CartSchema(BaseModel):
    """O objeto de carrinho completo enviado ao frontend."""
    id: int
    status: str
    coupon_code: Optional[str] = None
    observation: Optional[str] = None
    items: List[CartItemSchema]

    # Campos calculados em tempo real no backend
    subtotal: int
    discount: int
    total: int

    class ConfigDict:
        from_attributes = True

# =====================================================================================
# SEÇÃO 2: SCHEMAS DE ENTRADA (O que o Flutter envia para o backend)
# Estes schemas permanecem os mesmos - enxutos e seguros.
# =====================================================================================

class UpdateCartItemOptionInput(BaseModel):
    variant_option_id: int
    quantity: int

class UpdateCartItemVariantInput(BaseModel):
    variant_id: int
    options: List[UpdateCartItemOptionInput]

class UpdateCartItemInput(BaseModel):
    product_id: int
    category_id: int
    quantity: int = Field(..., ge=0)
    note: Optional[str] = None
    variants: Optional[List[UpdateCartItemVariantInput]] = None
    cart_item_id: Optional[int] = None # Para o modo de edição

class ApplyCouponInput(BaseModel):
    coupon_code: str