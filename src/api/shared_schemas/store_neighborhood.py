from pydantic import BaseModel


class StoreNeighborhoodBaseSchema(BaseModel):
    name: str
    city_id: int
    delivery_fee: int = 0
    free_delivery: bool = False
    is_active: bool = True

model_config = {
        "from_attributes": True
    }
class StoreNeighborhoodSchema(StoreNeighborhoodBaseSchema):
    id: int

    class Config:
        orm_mode = True
