from pydantic import BaseModel
from typing import Optional, List

from src.core.models import StoreNeighborhood


class StoreCityBaseSchema(BaseModel):
    name: str
    delivery_fee: int = 0
    is_active: bool = True
    neighborhoods: List[StoreNeighborhood] = []  # Relationship with neighborhoods


    model_config = {
        "from_attributes": True,
        "arbitrary_types_allowed": True # ADICIONE ESTA LINHA AQUI
    }

class StoreCitySchema(StoreCityBaseSchema):
    id: int


