# src/api/webhooks/chatbot_webhook.py

import os
from fastapi import APIRouter, Depends, Header, HTTPException

from src.api.admin.socketio.emitters import emit_chatbot_config_update
# NOVO: Importe a função de atualização geral da loja
from src.api.admin.utils.emit_updates import emit_store_updates
from src.api.schemas.chatbot_config import ChatbotWebhookPayload
from src.core import models
from src.core.database import GetDBDep

# --- Crie um router SÓ para webhooks ---
router = APIRouter(prefix="/webhooks", tags=["Webhooks"])

WEBHOOK_SECRET_KEY = os.getenv("CHATBOT_WEBHOOK_SECRET")
if not WEBHOOK_SECRET_KEY:
    raise ValueError("A variável de ambiente CHATBOT_WEBHOOK_SECRET não foi configurada.")


def verify_webhook_secret(x_webhook_secret: str = Header(...)):
    if x_webhook_secret != WEBHOOK_SECRET_KEY:
        raise HTTPException(status_code=403, detail="Acesso negado: Chave secreta do webhook inválida.")


# --- A Rota de Webhook no lugar certo ---
@router.post(
    "/chatbot/update",
    summary="Webhook para receber atualizações do serviço de Chatbot",
    dependencies=[Depends(verify_webhook_secret)],
    include_in_schema=False
)
async def chatbot_webhook(payload: ChatbotWebhookPayload, db: GetDBDep):
    """
    Esta rota é chamada pelo serviço de robô (Node.js) para nos dar
    o QR Code ou para nos informar que a conexão foi bem-sucedida.
    """

    print(f"🤖 Webhook do Chatbot recebido para loja {payload.lojaId}: status {payload.status}")
    store = db.query(models.Store).filter_by(id=payload.lojaId).first()
    if not store:
        print(f"❌ Loja {payload.lojaId} não encontrada")
        return {"status": "erro", "message": "Loja não encontrada"}

    # Validar status
    valid_statuses = ['awaiting_qr', 'connected', 'disconnected', 'error']
    if payload.status not in valid_statuses:
        print(f"❌ Status inválido: {payload.status}")
        return {"status": "erro", "message": "Status inválido"}

    config = db.query(models.StoreChatbotConfig).filter_by(store_id=payload.lojaId).first()
    if not config:
        config = models.StoreChatbotConfig(store_id=payload.lojaId)
        db.add(config)

    # Atualiza sempre o status
    config.connection_status = payload.status

    # NOVO: Lógica para limpar os dados em caso de desconexão ou erro
    if payload.status in ['disconnected', 'error']:
        config.last_qr_code = None
        config.whatsapp_name = None
        print(f"🧼 Sessão limpa no banco de dados para a loja {payload.lojaId}.")
    else:
        # Mantém os dados atualizados nos outros casos
        config.last_qr_code = payload.qrCode
        config.whatsapp_name = payload.whatsappName

    db.commit()

    # 1. Notifica a página específica de configuração do chatbot
    await emit_chatbot_config_update(db, payload.lojaId)

    # NOVO: 2. Notifica a aplicação sobre uma atualização geral na loja
    # Isso atualizará listas de lojas, dashboards, etc.
    await emit_store_updates(db, store.id)

    print(f"✅ Frontend notificado (específico e geral) sobre a atualização para loja {payload.lojaId}.")

    return {"status": "sucesso", "message": "Webhook processado."}