from datetime import time
from typing import List

from pydantic import BaseModel


class ProductAvailabilityCreate(BaseModel):
    weekday: int
    start_time: time
    end_time: time

class ProductCreateWithAvailability(BaseModel):
    name: str
    description: str
    base_price: int
    cost_price: int = 0
    available: bool
    category_id: int

    # outras propriedades...

    availabilities: List[ProductAvailabilityCreate] = []


