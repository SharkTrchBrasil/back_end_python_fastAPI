from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime

class StoreRatingCreate(BaseModel):
    rating: int = Field(..., ge=1, le=5)
    comment: Optional[str]

class StoreRatingOut(StoreRatingCreate):
    id: int
    store_id: int
    customer_id: Optional[int]


    class Config:
        orm_mode = True
