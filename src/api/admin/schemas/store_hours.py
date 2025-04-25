from pydantic import BaseModel
from datetime import time
from typing import List, Optional

class StoreHours(BaseModel):
    day_of_week: int  # 0 (Domingo) a 6 (Sábado)
    opening_time: time
    closing_time: time
    shift_number: int
    is_active: bool = True



