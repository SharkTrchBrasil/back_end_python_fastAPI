# Em src/api/schemas/chatbot.py

from pydantic import BaseModel, ConfigDict

from src.core.utils.enums import ChatbotMessageGroupEnum


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