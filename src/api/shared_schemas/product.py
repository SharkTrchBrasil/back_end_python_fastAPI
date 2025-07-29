from typing import Optional, List
from pydantic import BaseModel, Field, ConfigDict, computed_field


from .product_variant_link import ProductVariantLink as ProductVariantLinkOut

from src.core.aws import get_presigned_url
from ...core.models import Category


# --- Configuração Pydantic Base ---
class AppBaseModel(BaseModel):
    model_config = ConfigDict(from_attributes=True, extra="forbid")

# -------------------------------------------------
# 1. Schemas de Produto
# -------------------------------------------------

class ProductBase(AppBaseModel):
    """Campos essenciais que definem um produto."""
    name: str
    description: str
    base_price: int
    available: bool
    promotion_price: int
    featured: bool
    activate_promotion: bool
    ean: str
    cost_price: int
    stock_quantity: int
    control_stock: bool
    min_stock: int
    max_stock: int
    unit: str
    sold_count: int
    file_key: str | None = Field(default=None, exclude=True) # Exclui do JSON de resposta

class ProductCreate(ProductBase):
    """Schema para criar um novo produto. Note a ausência de 'variant_ids'."""
    category_id: int
    store_id: int # O store_id virá da URL, mas pode ser útil no corpo

class ProductUpdate(AppBaseModel):
    """Schema para atualizar um produto. Todos os campos são opcionais."""
    name: Optional[str] = None
    description: Optional[str] = None
    base_price: Optional[int] = None
    cost_price: Optional[int] = None
    available: Optional[bool] = None
    promotion_price: Optional[int] = None
    featured: Optional[bool] = None
    activate_promotion: Optional[bool] = None
    ean: Optional[str] = None
    stock_quantity: Optional[int] = None
    control_stock: Optional[bool] = None
    min_stock: Optional[int] = None
    max_stock: Optional[int] = None
    unit: Optional[str] = None
    category_id: Optional[int] = None
    file_key: Optional[str] = Field(default=None, exclude=True)


class ProductOut(ProductBase):
    """
    Schema de resposta da API. É declarativo e poderoso.
    Ele retorna as REGRAS e os complementos aninhados.
    """
    id: int
    category: Category

    # ✅ CORREÇÃO PRINCIPAL: Inclui a lista de 'ligações de variantes',
    # que contém tanto as regras quanto o template do grupo.

    variant_links: List["ProductVariantLinkOut"] = []

    @computed_field
    @property
    def image_path(self) -> str | None:
        """Gera a URL da imagem a partir da file_key."""
        return get_presigned_url(self.file_key) if self.file_key else None

# -------------------------------------------------
# 2. Schemas de Avaliação (ProductRating)
# -------------------------------------------------

class ProductRatingBase(AppBaseModel):
    rating: int = Field(..., ge=1, le=5)
    comment: Optional[str] = None

class ProductRatingCreate(ProductRatingBase):
    pass

class ProductRatingOut(ProductRatingBase):
    id: int
    product_id: int
    customer_id: int
    # ✅ Apenas atualizamos o estilo da configuração para Pydantic v2
    # model_config = ConfigDict(from_attributes=True) já é herdado de AppBaseModel


ProductOut.model_rebuild()