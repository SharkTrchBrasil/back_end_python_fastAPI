from pydantic import BaseModel, Field, computed_field

from src.api.admin.schemas.category import Category
from src.api.admin.schemas.supplier import Supplier
from src.api.admin.schemas.variant import ProductVariant
from src.core.aws import get_presigned_url


class Product(BaseModel):
    id: int
    name: str
    description: str
    base_price: int
    available: bool
    category: Category
    supplier: Supplier
    variants: list[ProductVariant]


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

    file_key: str = Field(exclude=True)

    @computed_field
    @property
    def image_path(self) -> str:
        return get_presigned_url(self.file_key)