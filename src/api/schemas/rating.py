from datetime import datetime

from dateutil.relativedelta import relativedelta
from pydantic import BaseModel, Field, model_validator
from typing import Optional


class StoreRatingCreate(BaseModel):
    stars: int = Field(..., ge=1, le=5)
    comment: Optional[str] = None
    store_id: int
    order_id: int




class ProductRatingCreate(BaseModel):
    stars: int = Field(..., ge=1, le=5)
    comment: Optional[str] = None
    product_id: int
    order_id: int




class RatingOut(BaseModel):
    id: int
    customer_name: Optional[str] = None
    stars: int
    is_active: bool
    comment: Optional[str]
    owner_reply: Optional[str]
    created_at: Optional[str] = None
    created_since: Optional[str] = None


    class Config:
        from_attributes = True

    @model_validator(mode='after')
    def set_created_since(self):
        if self.created_at:
            dt = datetime.fromisoformat(self.created_at)
            now = datetime.now(tz=dt.tzinfo)
            delta = relativedelta(now, dt)
            self.created_since = f"{delta.days} dias atrás"
        return self

class RatingsSummaryOut(BaseModel):
    average_rating: float = Field(..., alias="average_rating")
    total_ratings: int = Field(..., alias="total_ratings")
    distribution: dict[int, int]
    ratings: list[RatingOut]

    class Config:
        from_attributes = True
        populate_by_name = True

