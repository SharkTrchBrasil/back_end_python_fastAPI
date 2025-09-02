from __future__ import annotations

from pydantic import BaseModel, Field, ConfigDict

from src.api.schemas.category import Category
from src.api.schemas.product_minimal import ProductMinimal


# --- Schema Base ---
# Contém todos os campos que podem ser enviados ou recebidos
class ProductCategoryLinkBase(BaseModel):
    category_id: int
    price: int = Field(..., ge=0) # '...' torna o campo obrigatório
    cost_price: int | None = Field(None, ge=0)
    is_on_promotion: bool = False
    promotional_price: int | None = Field(None, ge=0)
    is_available: bool = True
    is_featured: bool = False
    display_order: int = 0
    pos_code: str | None = None



    model_config = ConfigDict(from_attributes=True)

# --- Schema para Criação (Wizard) ---
# Herda da base, já está perfeito para o wizard
class ProductCategoryLinkCreate(ProductCategoryLinkBase):
    pass

# --- Schema para Atualização (PATCH) ---
# Todos os campos são opcionais
class ProductCategoryLinkUpdate(BaseModel):
    price: int | None = Field(None, ge=0)
    cost_price: int | None = Field(None, ge=0)
    is_on_promotion: bool | None = None
    promotional_price: int | None = Field(None, ge=0)
    is_available: bool | None = None
    is_featured: bool | None = None
    display_order: int | None = None
    pos_code: str | None = None


class ProductCategoryLinkOut(ProductCategoryLinkBase):
    product_id: int

    # ✨ AGORA USA O SCHEMA MÍNIMO PARA EVITAR O LOOP DE IMPORTAÇÃO
    product: ProductMinimal


    model_config = ConfigDict(from_attributes=True)