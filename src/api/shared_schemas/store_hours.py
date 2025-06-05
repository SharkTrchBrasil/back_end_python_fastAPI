from pydantic import BaseModel
from datetime import time
from typing import List, Optional

class StoreHoursSchema(BaseModel):
    id: int
    store_id: int
    day_of_week: int
    open_time: str
    close_time: str
    shift_number: int
    is_active: bool

