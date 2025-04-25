from pydantic import BaseModel, ConfigDict


class ProductVariantOptionBase(BaseModel):
    name: str
    description: str
    price: int
    available: bool


class ProductVariantOptionCreate(ProductVariantOptionBase):
    model_config = ConfigDict(extra="forbid")


class ProductVariantOption(ProductVariantOptionBase):
    id: int

class ProductVariantOptionUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str | None = None
    description: str | None = None
    price: int | None = None
    available: bool | None = None