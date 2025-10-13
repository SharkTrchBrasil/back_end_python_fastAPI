from pydantic import BaseModel
from datetime import datetime
from typing import Optional

class SessionOut(BaseModel):
    """Schema para retornar informações de uma sessão ativa."""
    id: int
    sid: str
    device_name: Optional[str] = None
    device_type: Optional[str] = None
    platform: Optional[str] = None
    browser: Optional[str] = None
    ip_address: Optional[str] = None
    created_at: datetime
    last_activity: datetime
    is_current: bool = False  # Será marcado pelo endpoint

    class Config:
        from_attributes = True  # Novo nome no Pydantic v2 (era orm_mode)