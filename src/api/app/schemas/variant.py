# src/api/shared_schemas/product_variant.py

from pydantic import BaseModel, Field, ConfigDict

from src.api.app.schemas.variant_option import VariantOption
from src.api.shared_schemas.product_variant_product import ProductVariantProductSchema


class Variant(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    description: str
    min_quantity: int
    max_quantity: int
    repeatable: bool
    variant_links: list[ProductVariantProductSchema]
    options: list[VariantOption]
