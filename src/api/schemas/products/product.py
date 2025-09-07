from __future__ import annotations
from typing import Optional, List
from pydantic import BaseModel, Field, ConfigDict, computed_field

import logging

from .product_category_link import ProductCategoryLinkCreate, ProductCategoryLinkOut
from .bulk_actions import KitComponentOut
from .product_variant_link import ProductVariantLinkOut, ProductVariantLinkCreate
from .rating import RatingsSummaryOut

from src.core.aws import get_presigned_url, S3_PUBLIC_BASE_URL
from src.core.utils.enums import CashbackType, ProductType, FoodTagEnum

# Configurar logging
logger = logging.getLogger(__name__)


# --- Configuração Pydantic Base ---
class AppBaseModel(BaseModel):
    model_config = ConfigDict(from_attributes=True, extra="forbid")

# ✅ CRIE OS SCHEMAS PARA A NOVA ESTRUTURA DE PREÇO
class FlavorPriceBase(BaseModel):
    size_option_id: int
    price: int = Field(..., ge=0)

class FlavorPriceCreate(FlavorPriceBase):
    pass

class FlavorPriceOut(FlavorPriceBase):
    id: int
    class Config: from_attributes = True

class FlavorPriceUpdate(BaseModel):
    price: int = Field(..., ge=0)


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
    tags: list[FoodTagEnum] | None = None


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
    tags: List[FoodTagEnum] = []

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


class ProductUpdate(AppBaseModel):
    """Schema para atualizar um produto. Todos os campos são opcionais."""
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = Field(None, max_length=2000)
    featured: Optional[bool] = None
    ean: Optional[str] = Field(None, max_length=13)
    available: Optional[bool] = None
    tag: Optional[str] = Field(None, max_length=50)
    stock_quantity: Optional[int] = Field(None, ge=0)
    control_stock: Optional[bool] = None
    min_stock: Optional[int] = Field(None, ge=0)
    max_stock: Optional[int] = Field(None, ge=0)
    unit: Optional[str] = Field(None, max_length=10)
    file_key: Optional[str] = Field(default=None, exclude=True)
    cashback_type: Optional[CashbackType] = None
    cashback_value: Optional[int] = Field(None, ge=0)


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
    price: int = Field(..., ge=0) # Preço em centavos
    pos_code: str | None = None


class BulkAddToCategoryPayload(BaseModel):
    target_category_id: int
    products: list[ProductPriceInfo] = Field(..., min_items=1)





class ProductOut(Product):
    id: int = Field(..., ge=1)
    variant_links: List[ProductVariantLinkOut] = Field([], description="Variantes do produto")

    category_links: List[ProductCategoryLinkOut] = Field([], description="Categorias do produto")

    prices: List[FlavorPriceOut] = []  # Retorna a lista de preços por tamanho

    components: List[KitComponentOut] = Field([], description="Componentes do kit")
    rating: Optional[RatingsSummaryOut] = Field(None, description="Avaliação do produto")
    default_options: List[ProductDefaultOptionOut] = Field(default=[], exclude=True)

    @computed_field
    @property
    def image_path(self) -> str | None:
        return f"{S3_PUBLIC_BASE_URL}/{self.file_key}" if self.file_key else None

    @computed_field
    @property
    def default_option_ids(self) -> list[int]:
        return [default.variant_option_id for default in self.default_options] if self.default_options else []

    @computed_field
    @property
    def calculated_stock(self) -> int | None:
        """Calcula o estoque disponível considerando componentes para kits."""
        if self.product_type != ProductType.KIT or not self.components:
            return self.stock_quantity if self.control_stock else None

        try:
            possible_kits = []
            for item in self.components:
                if not item.component.control_stock:
                    continue
                stock_for_this_item = item.component.stock_quantity // item.quantity
                possible_kits.append(stock_for_this_item)

            return min(possible_kits) if possible_kits else None
        except Exception as e:
            logger.error(f"Error calculating stock for product {self.id}: {e}")
            return None

    # --- CAMPOS CALCULADOS OTIMIZADOS PARA PREÇO ---

    # @computed_field
    # @property
    # def price(self) -> int:
    #     """Retorna o menor preço entre todas as categorias."""
    #     if not self.category_links:
    #         logger.warning(f"Product {self.id if hasattr(self, 'id') else 'unknown'} has no category links")
    #         return 0
    #
    #     try:
    #         return min(link.price for link in self.category_links)
    #     except ValueError as e:
    #         logger.error(f"Error calculating price for product {self.id}: {e}")
    #         return 0
    #
    # @computed_field
    # @property
    # def cost_price(self) -> int | None:
    #     """Retorna o menor preço de custo entre as categorias (apenas se todas tiverem)."""
    #     if not self.category_links:
    #         return None
    #
    #     try:
    #         # Filtra apenas categorias com cost_price definido
    #         cost_prices = [link.cost_price for link in self.category_links if link.cost_price is not None]
    #         return min(cost_prices) if cost_prices else None
    #     except ValueError as e:
    #         logger.error(f"Error calculating cost price for product {self.id}: {e}")
    #         return None
    #
    # @computed_field
    # @property
    # def is_on_promotion(self) -> bool:
    #     """Verifica se há promoção em qualquer categoria."""
    #     return any(link.is_on_promotion for link in self.category_links) if self.category_links else False
    #
    # @computed_field
    # @property
    # def promotional_price(self) -> int | None:
    #     """Retorna o menor preço promocional ativo."""
    #     if not self.category_links:
    #         return None
    #
    #     try:
    #         # Filtra apenas promoções ativas com preço definido
    #         active_promotions = [
    #             link.promotional_price for link in self.category_links
    #             if link.is_on_promotion and link.promotional_price is not None
    #         ]
    #         return min(active_promotions) if active_promotions else None
    #     except ValueError as e:
    #         logger.error(f"Error calculating promotional price for product {self.id}: {e}")
    #         return None

    @computed_field
    @property
    def primary_category_id(self) -> int | None:
        """Retorna o ID da primeira categoria (útil para referência)."""
        return self.category_links[0].category_id if self.category_links else None

    @computed_field
    @property
    def has_multiple_prices(self) -> bool:
        """Indica se o produto tem preços diferentes em categorias diferentes."""
        if len(self.category_links) <= 1:
            return False

        first_price = self.category_links[0].price
        return any(link.price != first_price for link in self.category_links[1:])


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