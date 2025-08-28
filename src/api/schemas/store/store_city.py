# schemas/store/store_city.py
from typing import List
from pydantic import ConfigDict

from ..base_schema import AppBaseModel
from .store_neighborhood import StoreNeighborhoodSchema


class StoreCityBaseSchema(AppBaseModel):
    name: str
    delivery_fee: int = 0
    is_active: bool = True
    neighborhoods: List[StoreNeighborhoodSchema] = []

    model_config = ConfigDict(from_attributes=True, arbitrary_types_allowed=True)


class StoreCitySchema(StoreCityBaseSchema):
    id: int


class StoreCityOut(AppBaseModel):
    id: int
    model_config = ConfigDict(from_attributes=True)