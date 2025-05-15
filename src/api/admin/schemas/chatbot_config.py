# src/api/admin/schemas/chatbot_config.py
from pydantic import BaseModel
from datetime import datetime
from typing import Optional

class StoreChatbotConfigBase(BaseModel):
    whatsapp_number: Optional[str] = None
    whatsapp_name: Optional[str] = None
    connection_status: str = "disconnected"  # Adicione um valor padrão
    last_qr_code: Optional[str] = None
    last_connected_at: Optional[datetime] = None
    session_path: Optional[str] = None

class StoreChatbotConfigCreate(StoreChatbotConfigBase):
    pass

class StoreChatbotConfigUpdate(StoreChatbotConfigBase):
    pass

class StoreChatbotConfig(StoreChatbotConfigBase):
    id: int
    store_id: int

    class Config:
        orm_mode = True
