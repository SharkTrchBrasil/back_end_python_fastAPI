from pydantic import BaseModel
from typing import Optional, List


from src.api.shared_schemas.store_neighborhood import StoreNeighborhoodSchema


# Input: para criação/atualização (com todos os dados)
class StoreCityBaseSchema(BaseModel):
    name: str
    delivery_fee: int = 0
    is_active: bool = True
    neighborhoods: List[StoreNeighborhoodSchema] = []

    model_config = {
        "from_attributes": True,
        "arbitrary_types_allowed": True
    }

class StoreCitySchema(StoreCityBaseSchema):
    id: int

# Output: só retorna o id
class StoreCityOut(BaseModel):
    id: int

    class Config:
        orm_mode = True
