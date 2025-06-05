from pydantic import BaseModel, ConfigDict


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
