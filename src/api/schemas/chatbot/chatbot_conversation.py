# src/api/schemas/chatbot_conversation.py

from pydantic import BaseModel, ConfigDict
from datetime import datetime
from typing import Optional

class ChatbotConversationSchema(BaseModel):
    """
    Schema para serializar o resumo de uma conversa do chatbot.
    Usado para listar todas as conversas ativas de uma loja no painel de admin.
    """
    chat_id: str
    store_id: int
    customer_name: Optional[str] = None
    last_message_preview: Optional[str] = None
    last_message_timestamp: datetime
    unread_count: int

    # Configuração para permitir que o Pydantic leia os dados diretamente
    # de um objeto SQLAlchemy (ORM) do seu models.py.
    model_config = ConfigDict(from_attributes=True)