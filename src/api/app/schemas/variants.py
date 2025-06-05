# src/api/shared_schemas/product_variant.py

from pydantic import BaseModel, Field, ConfigDict

from src.api.app.schemas.product_variant_product import ProductVariantProductSchemaApp


class VariantOption(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int

    name: str
    description:  str | None
    price: int
    discount_price: int
    max_quantity: int
    available: bool
    is_free: bool

class Variant(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    description: str
    min_quantity: int
    max_quantity: int
    repeatable: bool
    variant_links: list[ProductVariantProductSchemaApp]
    options: list[VariantOption]
