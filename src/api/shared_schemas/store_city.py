from pydantic import BaseModel
from typing import Optional, List

from src.core.models import StoreNeighborhood


class StoreCityBaseSchema(BaseModel):
    name: str
    delivery_fee: int = 0
    is_active: bool = True
    neighborhoods: List[StoreNeighborhood] = []  # Relationship with neighborhoods

    model_config = {"from_attributes": True}

class StoreCitySchema(StoreCityBaseSchema):
    id: int


