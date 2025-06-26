from pydantic import BaseModel, ConfigDict

from src.api.shared_schemas.product import Product


class Coupon(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    product: Product | None = None
    code: str
    discount_percent: int | None
    discount_fixed: int | None
