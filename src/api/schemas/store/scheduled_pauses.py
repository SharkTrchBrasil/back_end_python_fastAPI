from pydantic import BaseModel, ConfigDict
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

    model_config = ConfigDict(from_attributes=True)