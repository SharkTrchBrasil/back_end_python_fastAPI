from typing import Annotated
from pydantic import BaseModel, Field, ConfigDict


# Variant schemas
class VariantBase(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: Annotated[str, Field(min_length=2, max_length=100, examples=["Variant ABC"])]
    description: Annotated[str, Field(min_length=0, max_length=255)]
    min_quantity: int
    max_quantity: int
    repeatable: bool
    available: bool


class Variant(VariantBase):
    model_config = ConfigDict(from_attributes=True, extra="forbid")
    id: int
    options: list["VariantOption"]  # use string annotation para evitar problemas


class VariantCreate(VariantBase):
    pass  # herdou extra="forbid"


class VariantUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: Annotated[str | None, Field(min_length=2, max_length=100, examples=["Variant ABC"], default=None)] = None
    description: Annotated[str | None, Field(min_length=0, max_length=255, default=None)] = None
    min_quantity: int | None = None
    max_quantity: int | None = None
    repeatable: bool | None = None
    available: bool | None = None


# VariantOption schemas
class VariantOptionBase(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: Annotated[str, Field(min_length=1, max_length=100)]
    description: Annotated[str, Field(min_length=0, max_length=255)]
    price: int
    discount_price: int
    max_quantity: int

    available: bool
    is_free: bool


class VariantOptionCreate(VariantOptionBase):
    pass  # herdou extra="forbid"


class VariantOption(VariantOptionBase):
    model_config = ConfigDict(from_attributes=True, extra="forbid")
    id: int


class VariantOptionUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str | None = None
    description: str | None = None
    price: int | None = None
    discount_price: int | None = None
    max_quantity: int | None = None
    available: bool | None = None
    is_free: bool | None = None
