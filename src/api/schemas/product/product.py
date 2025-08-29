from __future__ import annotations
from typing import Optional, List, TYPE_CHECKING
from pydantic import Field, computed_field

from src.core.aws import get_presigned_url
from src.core.utils.enums import CashbackType, ProductType
from src.api.schemas.category import ProductCategoryLinkCreate, ProductCategoryLinkOut
from src.api.schemas.rating import RatingsSummaryOut
from ..base_schema import AppBaseModel

if TYPE_CHECKING:
    from .product_variant_link import ProductVariantLink, ProductVariantLinkCreate
    from .kit_component import KitComponentOut

class ProductWizardCreate(AppBaseModel):
    name: str
    description: Optional[str] = None
    base_price: int
    cost_price: Optional[int] = 0
    ean: Optional[str] = None
    available: bool = True
    product_type: ProductType = ProductType.INDIVIDUAL
    stock_quantity: Optional[int] = 0
    control_stock: bool = False
    category_links: List[ProductCategoryLinkCreate] = Field(..., min_length=1)
    variant_links: List['ProductVariantLinkCreate'] = []

class ProductOut(AppBaseModel):
    id: int
    name: str
    description: Optional[str] = None
    base_price: int
    cost_price: Optional[int] = 0
    available: bool
    priority: int
    promotion_price: Optional[int] = 0
    featured: bool
    activate_promotion: bool
    ean: Optional[str] = None
    stock_quantity: Optional[int] = 0
    control_stock: bool
    min_stock: Optional[int] = 0
    max_stock: Optional[int] = 0
    unit: Optional[str] = "Unidade"
    sold_count: int
    cashback_type: CashbackType
    cashback_value: int
    product_type: ProductType
    category_links: List[ProductCategoryLinkOut] = []
    variant_links: List['ProductVariantLink'] = []
    components: List['KitComponentOut'] = []
    rating: Optional[RatingsSummaryOut] = None
    file_key: Optional[str] = Field(None, exclude=True)

    @computed_field
    @property
    def image_path(self) -> str | None:
        if self.file_key:
            return get_presigned_url(self.file_key)
        return None