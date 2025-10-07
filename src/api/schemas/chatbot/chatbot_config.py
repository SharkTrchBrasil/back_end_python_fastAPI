# Em src/api/schemas/chatbot_webhook.py
from typing import Optional

from pydantic import BaseModel, ConfigDict

from src.core.utils.enums import ChatbotMessageGroupEnum



class ChatbotWebhookPayload(BaseModel):
    """ Define a estrutura de dados que o serviço de robô nos enviará. """
    storeId: int
    status: str  # Ex: 'awaiting_qr', 'connected', 'disconnected'
    qrCode: str | None = None
    pairingCode: Optional[str] = None
    whatsappName: str | None = None


class StoreChatbotConfigSchema(BaseModel):
    whatsapp_name: str | None
    connection_status: str
    last_qr_code: str | None = None
    last_connection_code: Optional[str] = None
    model_config = ConfigDict(from_attributes=True)


# Schema para ler um template de mensagem (para construir a UI)
class ChatbotMessageTemplateSchema(BaseModel):
    message_key: str
    name: str
    description: str | None
    message_group: ChatbotMessageGroupEnum
    default_content: str
    available_variables: list[str] | None

    model_config = ConfigDict(from_attributes=True)


# Schema para ler a configuração de uma loja para uma mensagem
class StoreChatbotMessageSchema(BaseModel):
    template_key: str
    is_active: bool
    # O conteúdo final a ser usado (ou o customizado, ou o padrão do template)
    final_content: str
    template: ChatbotMessageTemplateSchema

    model_config = ConfigDict(from_attributes=True)


# Schema para ATUALIZAR a configuração de uma loja
class StoreChatbotMessageUpdateSchema(BaseModel):
    custom_content: str | None = None
    is_active: bool | None = None