

from pydantic import BaseModel
from datetime import date

class HolidayOut(BaseModel):
    date: date
    name: str