from datetime import datetime

from pydantic import BaseModel


class Totem(BaseModel):
    id: int
    totem_name: str
    created_at: datetime