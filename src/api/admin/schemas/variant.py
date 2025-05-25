from typing import Annotated

from pydantic import BaseModel, Field, ConfigDict

from src.api.admin.schemas.variant_option import VariantOption


class VariantBase(BaseModel):
    name: Annotated[str, Field(min_length=2, max_length=100, examples=["Variant ABC"])]
    description: Annotated[str, Field(min_length=0, max_length=255)]
    min_quantity: int
    max_quantity: int
    repeatable: bool
    available: bool


class Variant(VariantBase):
    id: int
    options: list[VariantOption]


class VariantCreate(VariantBase):
    model_config = ConfigDict(extra="forbid")


class VariantUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: Annotated[str | None, Field(min_length=2, max_length=100, examples=["Variant ABC"], default=None)]
    description: Annotated[str | None, Field(min_length=0, max_length=255, default=None)]
    min_quantity: int | None = None
    max_quantity: int | None = None
    repeatable: bool | None = None
    available: bool | None = None