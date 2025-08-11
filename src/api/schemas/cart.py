# Em um novo arquivo, ex: schemas/cart.py
from pydantic import BaseModel, Field
from typing import Optional, List


# --- Schemas aninhados primeiro ---

class CartItemVariantOptionSchema(BaseModel):
    variant_option_id: int
    quantity: int


class CartItemVariantSchema(BaseModel):
    variant_id: int
    options: List[CartItemVariantOptionSchema]


# Um schema leve para os dados do produto que o carrinho precisa exibir
class ProductSummarySchema(BaseModel):
    id: int
    name: str
    image_url: Optional[str] = None

    class ConfigDict:
        from_attributes = True  # Permite que o Pydantic leia atributos de objetos (ORM mode)


class CartItemSchema(BaseModel):
    id: int
    product: ProductSummarySchema  # Usamos o schema de resumo do produto
    quantity: int
    note: Optional[str] = None
    variants: List[CartItemVariantSchema]  # Pydantic valida a estrutura aninhada

    # Campos calculados em tempo real (não vêm do banco, são calculados no backend)
    unit_price: int
    total_price: int

    class ConfigDict:
        from_attributes = True


class CartSchema(BaseModel):
    id: int
    status: str
    coupon_code: Optional[str] = None
    observation: Optional[str] = None
    items: List[CartItemSchema]

    # Campos calculados em tempo real
    subtotal: int
    discount: int
    total: int

    class ConfigDict:
        from_attributes = True



# No mesmo arquivo schemas/cart.py

class UpdateCartItemOptionInput(BaseModel):
    variant_option_id: int
    quantity: int

class UpdateCartItemVariantInput(BaseModel):
    variant_id: int
    options: List[UpdateCartItemOptionInput]

class UpdateCartItemInput(BaseModel):
    product_id: int
    quantity: int = Field(..., ge=0) # Quantidade deve ser 0 ou maior
    note: Optional[str] = None
    variants: Optional[List[UpdateCartItemVariantInput]] = None

class ApplyCouponInput(BaseModel):
    coupon_code: str