# schemas/store/store_hours.py
from typing import Optional

from pydantic import ConfigDict

from ..base_schema import AppBaseModel


class StoreHoursBase(AppBaseModel):
    day_of_week: int
    open_time: str
    close_time: str
    shift_number: int
    is_active: bool


class StoreHoursCreate(StoreHoursBase):
    pass


class StoreHoursOut(StoreHoursBase):
    id: int
    store_id: int
    model_config = ConfigDict(from_attributes=True)