from pydantic import BaseModel, ConfigDict

from src.api.shared_schemas.product import ProductOut


class Coupon(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    product: ProductOut | None = None
    code: str
    discount_percent: int | None
    discount_fixed: int | None
