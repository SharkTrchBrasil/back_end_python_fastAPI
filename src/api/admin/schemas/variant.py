from typing import Annotated

from pydantic import BaseModel, Field, ConfigDict

from src.api.admin.schemas.product_variant_option import ProductVariantOption


class ProductVariantBase(BaseModel):
    name: Annotated[str, Field(min_length=2, max_length=30, examples=["Variant ABC"])]
    description: Annotated[str, Field(min_length=0, max_length=30)]
    min_quantity: int
    max_quantity: int
    repeatable: bool
    available: bool


class ProductVariant(ProductVariantBase):
    id: int
    options: list[ProductVariantOption]


class ProductVariantCreate(ProductVariantBase):
    model_config = ConfigDict(extra="forbid")


class ProductVariantUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: Annotated[str | None, Field(min_length=2, max_length=30, examples=["Variant ABC"], default=None)]
    description: Annotated[str | None, Field(min_length=0, max_length=30, default=None)]
    min_quantity: int | None = None
    max_quantity: int | None = None
    repeatable: bool | None = None
    available: bool | None = None