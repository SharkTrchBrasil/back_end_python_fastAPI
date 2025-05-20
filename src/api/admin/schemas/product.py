from typing import Optional, List, Annotated

from fastapi import Form
from pydantic import BaseModel, Field, computed_field

from src.api.admin.schemas.category import Category
from src.api.admin.schemas.variant import ProductVariant
from src.api.admin.services.forms import as_form
from src.core.aws import get_presigned_url


class ProductBase(BaseModel):
    name: str
    description: str
    base_price: int
    available: bool

    promotion_price: int
    featured: bool
    activate_promotion: bool

    ean: str
    code: str
    auto_code: bool
    extra_code: str
    cost_price: int

    stock_quantity: int
    control_stock: bool
    min_stock: int
    max_stock: int

    unit: str
    allow_fraction: bool
    observation: str
    location: str

    file_key: str


class Product(ProductBase):
    id: int
    category: Category
    variants: list[ProductVariant]

    file_key: str = Field(exclude=True)

    @computed_field
    @property
    def image_path(self) -> str:
        return get_presigned_url(self.file_key)


@as_form
class ProductCreate(BaseModel):
    name: str
    description: str
    base_price: int
    cost_price: int = 0
    available: bool
    category_id: int
    ean: str = ""
    code: str = ""
    auto_code: bool = True
    extra_code: str = ""
    stock_quantity: int = 0
    control_stock: bool = False
    min_stock: int = 0
    max_stock: int = 0
    unit: str = ""
    allow_fraction: bool = False
    observation: str = ""
    location: str = ""
    #store_id: int
    variant_ids: Optional[List[int]] = None


@as_form
class ProductUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    base_price: Optional[int] = None
    cost_price: Optional[int] = None
    available: Optional[bool] = None
    category_id: Optional[int] = None
    ean: Optional[str] = None
    code: Optional[str] = None
    auto_code: Optional[bool] = None
    extra_code: Optional[str] = None
    stock_quantity: Optional[int] = None
    control_stock: Optional[bool] = None
    min_stock: Optional[int] = None
    max_stock: Optional[int] = None
    unit: Optional[str] = None
    allow_fraction: Optional[bool] = None
    observation: Optional[str] = None
    location: Optional[str] = None
    promotion_price: Optional[int] = None
    activate_promotion: Optional[bool] = None
    featured: Optional[bool] = None
    variant_ids: Optional[List[int]] = None


class ProductOut(ProductBase):
    id: int
    category: Category
    variants: List[ProductVariant]

    file_key: str = Field(exclude=True)

    @computed_field
    @property
    def image_path(self) -> str:
        return get_presigned_url(self.file_key)

# from typing import Optional, List
#
# from pydantic import BaseModel, Field, computed_field
#
# from src.api.admin.schemas.category import Category
#
# from src.api.admin.schemas.variant import ProductVariant
# from src.core.aws import get_presigned_url
#
#
# class Product(BaseModel):
#     id: int
#     name: str
#     description: str
#     base_price: int
#     available: bool
#
#     promotion_price:int
#
#     features: bool
#     activate_promotion: bool
#
#     category: Category
#     variants: list[ProductVariant]
#
#
#     ean: str
#     code: str
#     auto_code: bool
#     extra_code: str
#     cost_price: int
#
#
#     stock_quantity: int
#     control_stock: bool
#     min_stock: int
#     max_stock: int
#
#     unit: str
#     allow_fraction: bool
#     observation: str
#     location: str
#
#     file_key: str = Field(exclude=True)
#
#     @computed_field
#     @property
#     def image_path(self) -> str:
#         return get_presigned_url(self.file_key)
#
#
# class ProductCreate(Product):
#     category_id: int
#     store_id: int
#     variant_ids: Optional[List[int]] = []
