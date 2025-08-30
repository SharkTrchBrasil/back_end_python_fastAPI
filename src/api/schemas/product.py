from typing import Optional, List
from pydantic import BaseModel, Field, ConfigDict, computed_field
from pydantic_core.core_schema import FieldValidationInfo

# ✅ CORRIGIDO: Importações diretas, sem dependência circular
from .product_category_link import ProductCategoryLinkCreate

from .category import CategoryOut
from .bulk_actions import KitComponentOut
from .product_variant_link import ProductVariantLinkOut, ProductVariantLinkCreate
from .rating import RatingsSummaryOut

from src.core.aws import get_presigned_url
from src.core.utils.enums import CashbackType, ProductType
from pydantic import field_validator # ✅ 1. Adicione este import
from typing import Any # ✅ Adicione este import também


# --- Configuração Pydantic Base ---
class AppBaseModel(BaseModel):
    model_config = ConfigDict(from_attributes=True, extra="forbid")


# -------------------------------------------------
# 1. Schemas de Produto
# -------------------------------------------------

class ProductWizardCreate(AppBaseModel):
    name: str
    description: Optional[str] = None
   # base_price: int
    #cost_price: Optional[int] = 0
    ean: Optional[str] = None
    available: bool = True
    product_type: ProductType = ProductType.INDIVIDUAL
    stock_quantity: Optional[int] = 0
    control_stock: bool = False
    category_links: List[ProductCategoryLinkCreate] = Field(..., min_length=1)

    # ✅ CORRIGIDO: Sem aspas! A classe foi importada diretamente.
    variant_links: List[ProductVariantLinkCreate] = []


class Product(AppBaseModel):
    """Campos essenciais que definem um produto."""
    name: str
    description: str
    #base_price: int
    product_type: ProductType = ProductType.INDIVIDUAL
    available: bool
   # promotion_price: int
    featured: bool
   # activate_promotion: bool
    ean: str
   # cost_price: int
    stock_quantity: int
    control_stock: bool
    min_stock: int
    max_stock: int
    unit: str
    sold_count: int
    file_key: str | None = Field(default=None, exclude=True)
    cashback_type: CashbackType = CashbackType.NONE
    cashback_value: int = 0


class ProductCreate(Product):
    """Schema para criar um novo produto."""
    category_id: int
    store_id: int


class ProductUpdate(AppBaseModel):
    """Schema para atualizar um produto. Todos os campos são opcionais."""
    name: Optional[str] = None
    description: Optional[str] = None
    # base_price: Optional[int] = None
    # cost_price: Optional[int] = None
    # available: Optional[bool] = None
    # promotion_price: Optional[int] = None

    featured: Optional[bool] = None

    activate_promotion: Optional[bool] = None
    ean: Optional[str] = None
    stock_quantity: Optional[int] = None
    control_stock: Optional[bool] = None
    min_stock: Optional[int] = None
    max_stock: Optional[int] = None
    unit: Optional[str] = None
    #category_id: Optional[int] = None
    file_key: Optional[str] = Field(default=None, exclude=True)
    cashback_type: Optional[CashbackType] = None
    cashback_value: Optional[int] = None


class ProductDefaultOptionOut(AppBaseModel):
    variant_option_id: int


class ProductOut(Product):
    """Schema de resposta da API."""
    id: int
    category: CategoryOut

    # ✅ CORRIGIDO: Sem aspas! A classe foi importada diretamente.
    variant_links: List[ProductVariantLinkOut] = []
    components: List[KitComponentOut] = []
    rating: Optional[RatingsSummaryOut] = None
    default_options: List[ProductDefaultOptionOut] = Field(default=[], exclude=True)

    @field_validator('category', mode='before')
    @classmethod
    def get_primary_category_from_links(cls, v: Any, info: FieldValidationInfo) -> Any:
        """
        Este validador executa ANTES da validação normal. Ele pega o objeto
        SQLAlchemy e extrai a categoria principal da lista de 'category_links'.
        """
        # ✅ CORREÇÃO FINAL: Usamos `info.instance` para acessar o objeto SQLAlchemy diretamente.
        # Nossos prints provaram que `instance.category_links` está carregado.
        if hasattr(info, 'instance') and info.instance.category_links:
            return info.instance.category_links[0].category

        raise ValueError("O produto não possui uma categoria principal vinculada.")

    @computed_field
    @property
    def image_path(self) -> str | None:
        return get_presigned_url(self.file_key) if self.file_key else None

    @computed_field
    @property
    def default_option_ids(self) -> list[int]:
        if not hasattr(self, 'default_options') or not self.default_options:
            return []
        return [default.variant_option_id for default in self.default_options]

    @computed_field
    @property
    def calculated_stock(self) -> int | None:
        if self.product_type != ProductType.KIT or not self.components:
            return self.stock_quantity if self.control_stock else None

        possible_kits = []
        for item in self.components:
            if not item.component.control_stock:
                continue
            stock_for_this_item = item.component.stock_quantity // item.quantity
            possible_kits.append(stock_for_this_item)

        if not possible_kits:
            return None

        return min(possible_kits)

    # ✅ --- NOVOS CAMPOS CALCULADOS PARA PREÇO --- ✅

    @computed_field
    @property
    def price(self) -> int:
        """Retorna o preço da categoria principal."""
        if self.category_links:
            return self.category_links[0].price
        return 0 # Valor padrão caso não haja link (pouco provável)

    @computed_field
    @property
    def cost_price(self) -> int | None:
        """Retorna o preço de custo da categoria principal."""
        if self.category_links:
            return self.category_links[0].cost_price
        return None

    @computed_field
    @property
    def is_on_promotion(self) -> bool:
        """Verifica se há promoção na categoria principal."""
        if self.category_links:
            return self.category_links[0].is_on_promotion
        return False

    @computed_field
    @property
    def promotional_price(self) -> int | None:
        """Retorna o preço promocional da categoria principal."""
        if self.category_links:
            return self.category_links[0].promotional_price
        return None


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