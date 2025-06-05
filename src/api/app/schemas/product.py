from pydantic import BaseModel, Field, computed_field, ConfigDict

from src.api.admin.schemas.product_variant_product import ProductVariantProductSchema
from src.api.app.schemas.category import Category
from src.core.aws import get_presigned_url
from src.core.models import ProductVariantProduct


class ProductVariantOption(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    description: str | None
    price: int


class ProductVariant(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    description: str
    min_quantity: int
    max_quantity: int
    repeatable: bool
    variant_links: list[ProductVariantProductSchema]
    options: list[ProductVariantOption]  # se quiser já trazer junto


class Product(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    description: str
    base_price: int
    category: Category
    variant_links: list[ProductVariantProductSchema]
    options: list[ProductVariantOption]  # se quiser já trazer junto
    file_key: str = Field(exclude=True)

    @computed_field
    @property
    def image_path(self) -> str:
        return get_presigned_url(self.file_key)

