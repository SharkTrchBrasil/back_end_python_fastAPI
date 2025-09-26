# src/api/schemas/chatbot_message.py

from pydantic import BaseModel, ConfigDict
from datetime import datetime
from typing import Optional, List

from src.api.schemas.orders.order import OrderDetails


class ChatbotMessageSchema(BaseModel):
    """
    Schema para serializar os dados de uma mensagem do chatbot para a API.
    """
    id: int
    store_id: int
    message_uid: str
    chat_id: str
    sender_id: str
    content_type: str
    text_content: Optional[str] = None
    media_url: Optional[str] = None
    media_mime_type: Optional[str] = None
    is_from_me: bool
    timestamp: datetime
    created_at: datetime

    # Configuração para permitir que o Pydantic leia os dados diretamente
    # de um objeto SQLAlchemy (ORM).
    model_config = ConfigDict(from_attributes=True)



# ✅ NOVO SCHEMA PARA O ESTADO INICIAL DO PAINEL DE CHAT
class ChatPanelInitialStateSchema(BaseModel):
    """
    Define a estrutura de dados completa que o painel de chat precisa
    ao ser inicializado: o histórico de mensagens e o pedido ativo do cliente.
    """
    messages: List[ChatbotMessageSchema]
    active_order: Optional[OrderDetails] = None

    model_config = ConfigDict(from_attributes=True)