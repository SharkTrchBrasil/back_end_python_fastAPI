from __future__ import annotations
from typing import Optional, List
from pydantic import BaseModel, Field, ConfigDict, computed_field

import logging

from .product_category_link import ProductCategoryLinkCreate, ProductCategoryLinkOut
from .bulk_actions import KitComponentOut
from .product_variant_link import ProductVariantLinkOut, ProductVariantLinkCreate
from .rating import RatingsSummaryOut

from src.core.aws import get_presigned_url, S3_PUBLIC_BASE_URL
from src.core.utils.enums import CashbackType, ProductType, FoodTagEnum, BeverageTagEnum

# Configurar logging
logger = logging.getLogger(__name__)


# --- Configuração Pydantic Base ---
class AppBaseModel(BaseModel):
    model_config = ConfigDict(from_attributes=True, extra="forbid")


# ✅ SCHEMAS DE PREÇO COMPLETOS E CORRIGIDOS
class FlavorPriceBase(BaseModel):
    size_option_id: int
    price: int = Field(..., ge=0)
    pos_code: str | None = None       # ✅ Adicionado
    is_available: bool = True


class FlavorPriceCreate(FlavorPriceBase):
    pass


class FlavorPriceOut(FlavorPriceBase):
    id: int

    model_config = ConfigDict(from_attributes=True)


# Este schema é para updates pontuais de um único preço
class FlavorPriceUpdate(BaseModel):
    price: int | None = Field(None, ge=0)
    pos_code: str | None = None       # ✅ Adicionado
    is_available: bool | None = None   # ✅ Adicionado
# ===================================================================
# WIZARD 1: Para Produtos Simples (ex: Coca-Cola, X-Bacon)
# ===================================================================

class SimpleProductWizardCreate(AppBaseModel):
    """
    Schema para criar um PRODUTO SIMPLES.
    O preço é definido diretamente no link com a categoria.
    """
    # --- Dados Básicos ---
    name: str = Field(..., min_length=1, max_length=255, description="Nome do produto")
    description: Optional[str] = Field(None, max_length=2000, description="Descrição do produto")
    ean: Optional[str] = Field(None, max_length=13, description="Código EAN do produto")
    available: bool = Field(True, description="Disponibilidade do produto")
    product_type: ProductType = Field(ProductType.INDIVIDUAL, description="Tipo do produto")
    stock_quantity: Optional[int] = Field(0, ge=0, description="Quantidade em estoque")
    control_stock: bool = Field(False, description="Se controla estoque")
    # ✅ CAMPO ADICIONADO AQUI
    master_product_id: int | None = None
    category_links: List[ProductCategoryLinkCreate] = Field(..., min_length=1, description="Links para categorias")

    variant_links: List[ProductVariantLinkCreate] = Field([], description="Links para variantes")

    unit: str | None = 'un'
    weight: int | None = None
    serves_up_to: int | None = None

    dietary_tags: list[FoodTagEnum] | None = None
    beverage_tags: list[BeverageTagEnum] | None = None


# ===================================================================
# WIZARD 2: Para Sabores de Itens Customizáveis (ex: Sabor Calabresa)
# ===================================================================

class FlavorWizardCreate(AppBaseModel):
    """
    Schema para criar um 'SABOR' (que é um Produto), como 'Calabresa' ou 'Frango'.
    O preço é definido por tamanho (OptionItem) e não por categoria.
    """
    # --- Dados Básicos (iguais ao SimpleProductWizardCreate) ---
    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = Field(None, max_length=2000)
    ean: Optional[str] = Field(None, max_length=13)
    available: bool = True
    product_type: ProductType = ProductType.INDIVIDUAL

    # --- Estoque (iguais ao SimpleProductWizardCreate) ---
    stock_quantity: int = Field(0, ge=0)
    control_stock: bool = False

    # --- Classificação ---
    dietary_tags: list[FoodTagEnum] | None = None
    beverage_tags: list[BeverageTagEnum] | None = None

    # --- Vínculos e Preços (Específicos deste wizard) ---
    parent_category_id: int
    prices: List[FlavorPriceCreate]


class Product(AppBaseModel):
    """Campos essenciais que definem um produto."""
    name: str = Field(..., min_length=1, max_length=255)
    description: str = Field("", max_length=2000)
    product_type: ProductType = Field(ProductType.INDIVIDUAL)
    available: bool = Field(True)
    featured: bool = Field(False)
    ean: str = Field("")
    stock_quantity: int = Field(0, ge=0)
    control_stock: bool = Field(False)
    min_stock: int = Field(0, ge=0)
    max_stock: int = Field(0, ge=0)
    unit: str = Field("un", max_length=10)
    sold_count: int = Field(0, ge=0)
    file_key: Optional[str] = Field(default=None, exclude=True)
    cashback_type: CashbackType = Field(CashbackType.NONE)
    cashback_value: int = Field(0, ge=0)
    master_product_id: int | None = None  # ✅ CAMPO ADICIONADO AQUI


class ProductUpdate(BaseModel):
    """ Schema para a atualização COMPLETA de um produto. """
    # --- Campos básicos (opcionais) ---
    name: str | None = None
    description: str | None = None
    ean: str | None = None
    available: bool | None = None
    featured: bool | None = None

    # ✅ 'priority' ADICIONADO AQUI
    priority: int | None = None

    # --- Estoque ---
    control_stock: bool | None = None
    stock_quantity: int | None = None
    min_stock: int | None = None
    max_stock: int | None = None

    # --- Cashback ---
    cashback_type: CashbackType | None = None
    cashback_value: int | None = None

    # --- Atributos ---
    unit: str | None = None
    weight: int | None = None
    serves_up_to: int | None = None
    dietary_tags: list[FoodTagEnum] | None = None
    beverage_tags: list[BeverageTagEnum] | None = None

    # --- Vínculos (para sincronização completa) ---
    category_links: list[ProductCategoryLinkCreate] | None = None
    variant_links: list[ProductVariantLinkCreate] | None = None
    prices: list[FlavorPriceCreate] | None = None


class ProductDefaultOptionOut(AppBaseModel):
    variant_option_id: int = Field(..., ge=1)


class ProductNestedOut(Product):
    id: int = Field(..., ge=1)

    @computed_field
    @property
    def image_path(self) -> str | None:
        return f"{S3_PUBLIC_BASE_URL}/{self.file_key}" if self.file_key else None


class ProductPriceInfo(BaseModel):
    product_id: int
    price: int = Field(..., ge=0)
    pos_code: str | None = None


# ✅ ESTE É O SCHEMA CORRIGIDO QUE VOCÊ PRECISA USAR
class BulkCategoryUpdatePayload(BaseModel):
    target_category_id: int

    products: list[ProductPriceInfo] = Field(..., min_items=1)


# ✅ SCHEMA DE SAÍDA FINALIZADO
class ProductOut(AppBaseModel):
    id: int
    name: str
    description: str | None
    product_type: ProductType
    available: bool
    featured: bool
    ean: str | None
    stock_quantity: int
    control_stock: bool
    min_stock: int
    max_stock: int
    unit: str
    sold_count: int
    cashback_type: CashbackType
    cashback_value: int
    master_product_id: int | None

    # Atributos
    serves_up_to: int | None
    weight: int | None
    dietary_tags: List[FoodTagEnum]
    beverage_tags: List[BeverageTagEnum]

    # Relacionamentos
    variant_links: List[ProductVariantLinkOut]
    category_links: List[ProductCategoryLinkOut]
    prices: List[FlavorPriceOut]
    components: List[KitComponentOut]


# -------------------------------------------------
# 2. Schemas de Avaliação (ProductRating)
# -------------------------------------------------

class ProductRatingBase(AppBaseModel):
    rating: int = Field(..., ge=1, le=5, description="Avaliação de 1 a 5 estrelas")
    comment: Optional[str] = Field(None, max_length=1000, description="Comentário opcional")


class ProductRatingCreate(ProductRatingBase):
    pass


class ProductRatingOut(ProductRatingBase):
    id: int = Field(..., ge=1, description="ID da avaliação")
    product_id: int = Field(..., ge=1, description="ID do produto avaliado")
    customer_id: int = Field(..., ge=1, description="ID do cliente que avaliou")