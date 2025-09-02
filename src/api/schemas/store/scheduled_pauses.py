from pydantic import BaseModel
from datetime import datetime

class ScheduledPauseBase(BaseModel):
    reason: str | None = None
    start_time: datetime
    end_time: datetime

class ScheduledPauseCreate(ScheduledPauseBase):
    pass

class ScheduledPauseOut(ScheduledPauseBase):
    id: int
    is_active: bool

    class Config:
        from_attributes = True # Antigo orm_mode = True