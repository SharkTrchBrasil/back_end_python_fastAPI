# src/api/webhooks/chatbot_webhook.py

import os
from fastapi import APIRouter, Depends, Header, HTTPException

from src.api.admin.socketio.emitters import emit_chatbot_config_update
from src.api.admin.utils.emit_updates import emit_store_updates
from src.api.schemas.chatbot.chatbot_config import ChatbotWebhookPayload
from src.core import models
from src.core.database import GetDBDep

router = APIRouter(prefix="/webhooks", tags=["Webhooks"])

WEBHOOK_SECRET_KEY = os.getenv("CHATBOT_WEBHOOK_SECRET")
if not WEBHOOK_SECRET_KEY:
    raise ValueError("A variável de ambiente CHATBOT_WEBHOOK_SECRET não foi configurada.")

def verify_webhook_secret(x_webhook_secret: str = Header(...)):
    if x_webhook_secret != WEBHOOK_SECRET_KEY:
        raise HTTPException(status_code=403, detail="Acesso negado: Chave secreta do webhook inválida.")



@router.post(
    "/chatbot/update",
    summary="Webhook para receber atualizações do serviço de Chatbot",
    dependencies=[Depends(verify_webhook_secret)],
    include_in_schema=False
)


async def chatbot_webhook(payload: ChatbotWebhookPayload, db: GetDBDep):
    print(f"🤖 Webhook do Chatbot recebido para loja {payload.storeId}: status {payload.status}")

    store = db.query(models.Store).filter_by(id=payload.storeId).first()
    if not store:
        print(f"❌ Loja {payload.storeId} não encontrada")
        return {"status": "erro", "message": "Loja não encontrada"}

    # ✅ EXPANSÃO: Adicionar suporte para pairing code
    valid_statuses = ['awaiting_qr', 'awaiting_pairing_code', 'connected', 'disconnected', 'error']
    if payload.status not in valid_statuses:
        print(f"❌ Status inválido: {payload.status}")
        return {"status": "erro", "message": "Status inválido"}

    config = db.query(models.StoreChatbotConfig).filter_by(store_id=payload.storeId).first()
    if not config:
        config = models.StoreChatbotConfig(store_id=payload.storeId)
        db.add(config)

    config.connection_status = payload.status

    if payload.status in ['disconnected', 'error']:
        config.last_qr_code = None
        config.whatsapp_name = None
        # ✅ CORRIGIDO: Usando o nome do campo do modelo
        config.last_connection_code = None
    elif payload.status == 'awaiting_pairing_code':
        # ✅ CORRIGIDO: Usando o nome do campo do modelo
        config.last_connection_code = payload.pairingCode
        config.last_qr_code = None
    elif payload.status == 'awaiting_qr': # Adicionado para clareza
        config.last_qr_code = payload.qrCode
        config.whatsapp_name = None # Nome só vem quando conectado
        config.last_connection_code = None
    elif payload.status == 'connected':
        config.whatsapp_name = payload.whatsappName
        # Limpa os códigos após a conexão ser bem-sucedida
        config.last_qr_code = None
        config.last_connection_code = None

    db.commit()

    await emit_chatbot_config_update(db, payload.storeId)
    await emit_store_updates(db, store.id)

    print(f"✅ Frontend notificado sobre atualização para loja {payload.storeId}.")

    return {"status": "sucesso", "message": "Webhook processado."}