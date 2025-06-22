from pydantic import BaseModel
from typing import Optional, List


from src.api.shared_schemas.store_neighborhood import StoreNeighborhoodBaseSchema


class StoreCityBaseSchema(BaseModel):
    name: str
    delivery_fee: int = 0
    is_active: bool = True

    neighborhoods: List[StoreNeighborhoodBaseSchema] = []


    model_config = {
        "from_attributes": True,
        "arbitrary_types_allowed": True # Mantenha esta linha
    }

class StoreCitySchema(StoreCityBaseSchema):
    id: int



class StoreCityOut(BaseModel):
    id: int
    name: str
    delivery_fee: int = 0

    class Config:
        orm_mode = True