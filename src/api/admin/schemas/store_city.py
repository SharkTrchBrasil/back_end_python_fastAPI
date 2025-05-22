from pydantic import BaseModel
from typing import Optional, List


class StoreCityBaseSchema(BaseModel):
    name: str
    state_code: str
    delivery_fee: float = 0.0
    store_id: int


class StoreCitySchema(StoreCityBaseSchema):
    id: int

    class Config:
        orm_mode = True
