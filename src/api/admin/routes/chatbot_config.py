# src/api/admin/routers/chatbot_config.py - VERSÃO COMPLETA
from fastapi import APIRouter, HTTPException, Depends
from typing import List, Optional
from pydantic import BaseModel, Field

from src.api.admin.services.chatbot.chatbot_client import chatbot_client
from src.core.database import GetDBDep
from src.core.dependencies import GetStoreDep
from src.core import models

from src.api.admin.socketio.emitters import admin_emit_store_updated
from src.api.schemas.chatbot.chatbot_config import StoreChatbotMessageSchema, StoreChatbotMessageUpdateSchema

router = APIRouter(tags=["Chatbot Config"], prefix="/stores/{store_id}/chatbot-config")


# ✅ SCHEMAS
class ConnectRequest(BaseModel):
    method: str = Field(..., description="Método de conexão: 'qr' ou 'pairing'")
    phone_number: Optional[str] = Field(None, description="Número de telefone, obrigatório se o método for 'pairing'")


class ChatbotStatusUpdate(BaseModel):
    isActive: bool


# ✅ ROTAS DE MENSAGENS (RESTAURADAS)
@router.get("", response_model=List[StoreChatbotMessageSchema])
def get_all_message_configs(store: GetStoreDep, db: GetDBDep):
    """Obtém todas as configurações de mensagem do chatbot"""
    all_templates = db.query(models.ChatbotMessageTemplate).all()
    store_configs_list = db.query(models.StoreChatbotMessage).filter_by(store_id=store.id).all()
    store_configs_map = {config.template_key: config for config in store_configs_list}

    final_configs = []
    for template in all_templates:
        store_config = store_configs_map.get(template.message_key)
        final_config_obj = {
            "template_key": template.message_key,
            "is_active": store_config.is_active if store_config else True,
            "final_content": store_config.custom_content if store_config and store_config.custom_content else template.default_content,
            "template": template
        }
        final_configs.append(final_config_obj)

    return final_configs


@router.patch("/{message_key}", response_model=StoreChatbotMessageSchema)
async def update_message_config(
        message_key: str,
        config_update: StoreChatbotMessageUpdateSchema,
        store: GetStoreDep,
        db: GetDBDep
):
    """Atualiza uma configuração de mensagem específica"""
    # Validar template
    template = db.query(models.ChatbotMessageTemplate).filter_by(message_key=message_key).first()
    if not template:
        raise HTTPException(status_code=404, detail=f"Template de mensagem '{message_key}' não encontrado.")

    # Buscar ou criar configuração da loja
    db_config = db.query(models.StoreChatbotMessage).filter_by(
        store_id=store.id,
        template_key=message_key
    ).first()

    if not db_config:
        db_config = models.StoreChatbotMessage(store_id=store.id, template_key=message_key)
        db.add(db_config)

    # Aplicar atualizações
    update_data = config_update.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_config, key, value)

    db.commit()
    db.refresh(db_config)

    # Notificar frontend
    await admin_emit_store_updated(db, store.id)

    return {
        "template_key": db_config.template_key,
        "is_active": db_config.is_active,
        "final_content": db_config.custom_content if db_config.custom_content else template.default_content,
        "template": template
    }


# ✅ ROTAS DE STATUS DO CHATBOT
@router.post("/update-status")
async def update_chatbot_status(
        status_update: ChatbotStatusUpdate,
        store: GetStoreDep,
        db: GetDBDep
):
    """Ativa ou desativa o chatbot (compatível com Dart)"""
    config = db.query(models.StoreChatbotConfig).filter_by(store_id=store.id).first()

    if not config:
        raise HTTPException(status_code=404, detail="Configuração do chatbot não encontrada")

    if config.connection_status != 'connected':
        raise HTTPException(status_code=409, detail="Chatbot precisa estar conectado para alterar status")

    # Atualizar status
    config.is_active = status_update.isActive
    db.commit()

    # Notificar serviço Node.js
    try:
        success = await chatbot_client.update_status(store.id, status_update.isActive)
        if not success:
            print(f"⚠️ Status atualizado localmente, mas falha ao notificar Node.js")
    except Exception as e:
        print(f"⚠️ Erro ao notificar Node.js: {e}")

    await admin_emit_store_updated(db, store.id)

    action = "ativado" if status_update.isActive else "pausado"
    return {
        "message": f"Chatbot {action} com sucesso",
        "isActive": config.is_active
    }



# ✅ ROTAS DE CONEXÃO
@router.post("/connect")
async def conectar_whatsapp(
        request_data: ConnectRequest,
        store: GetStoreDep,
        db: GetDBDep
):
    """Conecta WhatsApp de forma robusta"""
    method = request_data.method
    phone_number = request_data.phone_number

    # Validações
    if method not in ["qr", "pairing"]:
        raise HTTPException(400, "Método deve ser 'qr' ou 'pairing'")

    if method == "pairing" and not phone_number:
        raise HTTPException(400, "phone_number obrigatório para pairing")

    # Verificar se já existe conexão ativa
    config = db.query(models.StoreChatbotConfig).filter_by(store_id=store.id).first()
    if config and config.connection_status in ["pending", "awaiting_qr", "awaiting_pairing_code", "connected"]:
        raise HTTPException(409, f"Já existe uma conexão com status: {config.connection_status}")

    # Criar/atualizar configuração
    if not config:
        config = models.StoreChatbotConfig(store_id=store.id, is_active=True)
        db.add(config)

    config.connection_status = "pending"
    config.last_qr_code = None
    config.whatsapp_name = None
    db.commit()

    # Iniciar sessão no Node.js
    success = await chatbot_client.start_session(
        store_id=store.id,
        method=method,
        phone_number=phone_number
    )

    if not success:
        config.connection_status = "error"
        db.commit()
        raise HTTPException(503, "Falha ao iniciar sessão no serviço de chatbot")

    await admin_emit_store_updated(db, store.id)
    return {"message": "Solicitação de conexão enviada ao serviço de chatbot"}


@router.delete("/disconnect")
async def desconectar_whatsapp(store: GetStoreDep, db: GetDBDep):
    """Desconecta WhatsApp"""
    success = await chatbot_client.disconnect_session(store.id)

    if not success:
        raise HTTPException(503, "Falha ao desconectar do serviço de chatbot")

    # Atualizar status no banco
    config = db.query(models.StoreChatbotConfig).filter_by(store_id=store.id).first()
    if config:
        config.connection_status = 'disconnected'
        config.whatsapp_name = None
        config.whatsapp_number = None
        config.last_qr_code = None
        config.last_connection_code = None
        db.commit()
        await admin_emit_store_updated(db, store.id)

    return {"message": "Solicitação de desconexão processada com sucesso"}