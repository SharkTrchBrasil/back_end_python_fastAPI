# schemas/store/store_neighborhood.py
from pydantic import ConfigDict
from ..base_schema import AppBaseModel


class StoreNeighborhoodBaseSchema(AppBaseModel):
    name: str
    city_id: int
    delivery_fee: int = 0
    free_delivery: bool = False
    is_active: bool = True

    model_config = ConfigDict(from_attributes=True, arbitrary_types_allowed=True)


class StoreNeighborhoodSchema(StoreNeighborhoodBaseSchema):
    id: int
    model_config = ConfigDict(from_attributes=True, arbitrary_types_allowed=True)