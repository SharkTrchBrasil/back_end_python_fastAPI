# schemas/rating/rating.py
from datetime import datetime
from dateutil.relativedelta import relativedelta
from pydantic import Field, model_validator
from typing import Optional

from ..base_schema import AppBaseModel


class StoreRatingCreate(AppBaseModel):
    stars: int = Field(..., ge=1, le=5)
    comment: Optional[str] = None
    store_id: int
    order_id: int


class ProductRatingCreate(AppBaseModel):
    stars: int = Field(..., ge=1, le=5)
    comment: Optional[str] = None
    product_id: int
    order_id: int


class RatingOut(AppBaseModel):
    id: int
    customer_name: Optional[str] = None
    stars: int
    is_active: bool
    comment: Optional[str] = None
    owner_reply: Optional[str] = None
    created_at: Optional[str] = None
    created_since: Optional[str] = None

    @model_validator(mode='after')
    def set_created_since(self):
        if self.created_at:
            dt = datetime.fromisoformat(self.created_at)
            now = datetime.now(tz=dt.tzinfo)
            delta = relativedelta(now, dt)

            if delta.years > 0:
                self.created_since = f"{delta.years} ano{'s' if delta.years > 1 else ''} atrás"
            elif delta.months > 0:
                self.created_since = f"{delta.months} mes{'es' if delta.months > 1 else ''} atrás"
            elif delta.days > 0:
                self.created_since = f"{delta.days} dia{'s' if delta.days > 1 else ''} atrás"
            elif delta.hours > 0:
                self.created_since = f"{delta.hours} hora{'s' if delta.hours > 1 else ''} atrás"
            elif delta.minutes > 0:
                self.created_since = f"{delta.minutes} minuto{'s' if delta.minutes > 1 else ''} atrás"
            else:
                self.created_since = "Agora mesmo"

        return self


class RatingsSummaryOut(AppBaseModel):
    average_rating: float = Field(..., alias="average_rating")
    total_ratings: int = Field(..., alias="total_ratings")
    distribution: dict[int, int]
    ratings: list[RatingOut]

    model_config = {
        "populate_by_name": True
    }