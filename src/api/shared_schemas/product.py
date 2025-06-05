from typing import Optional, List
from pydantic import BaseModel, Field, computed_field

from src.api.shared_schemas.category import Category
from src.api.shared_schemas.variant import Variant
from src.core.aws import get_presigned_url


# BASE SHARED MODEL
class Product(BaseModel):
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

    class Config:
        orm_mode = True


# INPUT MODEL FOR CREATION
class ProductCreate(Product):
    category_id: int
    store_id: int
    variant_ids: Optional[List[int]] = []


# INPUT MODEL FOR UPDATE
class ProductUpdate(BaseModel):
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
    variant_ids: Optional[List[int]] = None

    class Config:
        orm_mode = True


# OUTPUT MODEL FOR API RESPONSE
class ProductOut(Product):
    id: int
    category: Category
    variants: List[Variant] = []


    file_key: str = Field(exclude=True)

    @computed_field
    @property
    def image_path(self) -> str:
        return get_presigned_url(self.file_key)

    @classmethod
    def from_orm_obj(cls, orm_product) -> "ProductOut":
        variants = [link.variant for link in getattr(orm_product, "variant_links", []) or []]

        return cls(
            id=orm_product.id,
            name=orm_product.name,
            description=orm_product.description,
            base_price=orm_product.base_price,
            available=orm_product.available,
            promotion_price=orm_product.promotion_price,
            featured=orm_product.featured,
            activate_promotion=orm_product.activate_promotion,
            ean=orm_product.ean,

            cost_price=orm_product.cost_price,
            stock_quantity=orm_product.stock_quantity,
            control_stock=orm_product.control_stock,
            min_stock=orm_product.min_stock,
            max_stock=orm_product.max_stock,
            unit=orm_product.unit,

            file_key=orm_product.file_key,
            category=orm_product.category,
            variants=variants
        )
