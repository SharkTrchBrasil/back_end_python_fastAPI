from pydantic import BaseModel
from typing import Optional, List


class StoreCityBaseSchema(BaseModel):
    name: str
    delivery_fee: int = 0
    is_active: bool = True


class StoreCitySchema(StoreCityBaseSchema):
    id: int


