from pydantic import BaseModel, ConfigDict


class VariantOptionBase(BaseModel):
    name: str
    description: str
    price: int
    available: bool


class VariantOptionCreate(VariantOptionBase):
    model_config = ConfigDict(extra="forbid")


class VariantOption(VariantOptionBase):
    id: int

class VariantOptionUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str | None = None
    description: str | None = None
    price: int | None = None
    available: bool | None = None