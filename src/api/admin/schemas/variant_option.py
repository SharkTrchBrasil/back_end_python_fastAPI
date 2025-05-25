from pydantic import BaseModel, ConfigDict


class VariantOptionBase(BaseModel):
    name: str
    description: str
    price: int
    discount_price: int
    max_quantity: int

    available: bool
    is_free: bool


class VariantOptionCreate(VariantOptionBase):
    model_config = ConfigDict(extra="forbid")


class VariantOption(VariantOptionBase):
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