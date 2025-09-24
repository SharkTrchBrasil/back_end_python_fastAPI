# src/api/admin/routers/chatbot_webhook.py

import os
from typing import List
from fastapi import APIRouter, HTTPException, Depends
import httpx

from src.api.admin.socketio.emitters import admin_emit_store_updated
from src.api.admin.utils.emit_updates import emit_store_updates
from src.api.schemas.chatbot_config import StoreChatbotMessageSchema, StoreChatbotMessageUpdateSchema
from src.core import models
from src.core.database import GetDBDep
from src.core.dependencies import GetStoreDep

async def get_async_http_client() -> httpx.AsyncClient:
    async with httpx.AsyncClient() as client:
        yield client

CHATBOT_SERVICE_URL = os.getenv("CHATBOT_SERVICE_URL")
CHATBOT_WEBHOOK_SECRET = os.getenv("CHATBOT_WEBHOOK_SECRET")

if not CHATBOT_SERVICE_URL or not CHATBOT_WEBHOOK_SECRET:
    raise ValueError("As variáveis CHATBOT_SERVICE_URL e CHATBOT_WEBHOOK_SECRET são obrigatórias.")

router = APIRouter(tags=["Chatbot Config"], prefix="/stores/{store_id}/chatbot-config")

# --- SUAS ROTAS DE GET E PATCH (QUE JÁ ESTAVAM PERFEITAS) ---
@router.get("", response_model=List[StoreChatbotMessageSchema])
def get_all_message_configs(store: GetStoreDep, db: GetDBDep):
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
async def update_message_config(message_key: str, config_update: StoreChatbotMessageUpdateSchema, store: GetStoreDep, db: GetDBDep):
    template = db.query(models.ChatbotMessageTemplate).filter_by(message_key=message_key).first()
    if not template:
        raise HTTPException(status_code=404, detail=f"Message template '{message_key}' not found.")
    db_config = db.query(models.StoreChatbotMessage).filter_by(store_id=store.id, template_key=message_key).first()
    if not db_config:
        db_config = models.StoreChatbotMessage(store_id=store.id, template_key=message_key)
        db.add(db_config)
    update_data = config_update.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_config, key, value)
    db.commit()
    db.refresh(db_config)
    await admin_emit_store_updated(db, store.id)
    return {
        "template_key": db_config.template_key,
        "is_active": db_config.is_active,
        "final_content": db_config.custom_content if db_config.custom_content else template.default_content,
        "template": template
    }


@router.post("/toggle-status", summary="Ativa ou desativa as respostas do chatbot")
async def toggle_chatbot_status(store: GetStoreDep, db: GetDBDep, http_client: httpx.AsyncClient = Depends(get_async_http_client)):
    config = db.query(models.StoreChatbotConfig).filter_by(store_id=store.id).first()
    if not config or config.connection_status != 'connected':
        raise HTTPException(status_code=409, detail="O chatbot não está conectado, então não pode ser ativado ou desativado.")

    # Inverte o status atual (True vira False, False vira True)
    config.is_active = not config.is_active
    db.commit()
    db.refresh(config)

    # Notifica o serviço Node.js sobre a mudança de estado
    try:
        update_url = f"{CHATBOT_SERVICE_URL}/update-status"
        headers = {'x-webhook-secret': CHATBOT_WEBHOOK_SECRET}
        payload = {"lojaId": store.id, "isActive": config.is_active}

        await http_client.post(update_url, json=payload, headers=headers, timeout=10.0)
    except Exception as e:
        # Se a notificação falhar, não desfazemos a ação, mas registramos o erro
        print(f"AVISO: O estado do chatbot para a loja {store.id} foi alterado para {config.is_active}, mas falhou ao notificar o serviço Node.js. Erro: {e}")

    # Notifica o frontend sobre a mudança para atualizar a UI
    await admin_emit_store_updated(db, store.id)

    return {"message": f"Chatbot foi {'ativado' if config.is_active else 'pausado'}.", "isActive": config.is_active}




@router.post("/connect")
async def conectar_whatsapp(store_id: int, db: GetDBDep,
                            http_client: httpx.AsyncClient = Depends(get_async_http_client)):
    iniciar_sessao_url = f"{CHATBOT_SERVICE_URL}/api/iniciar-sessao"  # Verifique se o /api está correto
    config = db.query(models.StoreChatbotConfig).filter_by(store_id=store_id).first()

    # --- LÓGICA CORRIGIDA E ESSENCIAL ---
    if config:
        # Se já existe uma configuração, vamos decidir o que fazer com base no status
        if config.connection_status in ["pending", "awaiting_qr", "connected"]:
            # Se uma conexão já está em andamento ou ativa, bloqueia a nova solicitação para evitar duplicidade.
            raise HTTPException(
                status_code=409,  # Conflict
                detail=f"Uma conexão já está ativa ou pendente com o status: {config.connection_status}."
            )

        # SE O STATUS FOR 'disconnected' ou 'error', NÓS REUTILIZAMOS O REGISTRO! (ESTA É A CORREÇÃO)
        print(
            f"[LOJA {store_id}] Reutilizando configuração com status '{config.connection_status}' para iniciar uma nova conexão.")
        config.connection_status = "pending"
        config.last_qr_code = None
        config.whatsapp_name = None
        config.is_active = True

    else:
        # Se não existe nenhuma configuração, criamos uma nova.
        print(f"[LOJA {store_id}] Criando nova configuração para iniciar a conexão.")
        config = models.StoreChatbotConfig(store_id=store_id, connection_status="pending", is_active=True)
        db.add(config)

    db.commit()
    await admin_emit_store_updated(db, store_id)  # Notifica o frontend que estamos 'pendente'

    # --- O RESTO DA FUNÇÃO CONTINUA IGUAL ---
    try:
        headers = {'x-webhook-secret': CHATBOT_WEBHOOK_SECRET}
        response = await http_client.post(iniciar_sessao_url, json={"lojaId": store_id}, headers=headers, timeout=15.0)
        response.raise_for_status()
        return {"message": "Solicitação de conexão enviada ao serviço de chatbot"}
    except (httpx.RequestError, httpx.HTTPStatusError) as e:
        config.connection_status = "error"
        db.commit()
        await admin_emit_store_updated(db, store_id)
        raise HTTPException(status_code=503, detail=f"Erro de comunicação com o serviço de chatbot: {e}")



@router.post("/disconnect", status_code=200)
async def desconectar_whatsapp(store: GetStoreDep, db: GetDBDep, http_client: httpx.AsyncClient = Depends(get_async_http_client)):
    desconectar_url = f"{CHATBOT_SERVICE_URL}/desconectar"
    headers = {'x-webhook-secret': CHATBOT_WEBHOOK_SECRET}

    try:
        response = await http_client.post(
            desconectar_url,
            json={"lojaId": store.id},
            headers=headers, # <-- Chave de segurança adicionada
            timeout=15.0
        )
        response.raise_for_status()
    except (httpx.RequestError, httpx.HTTPStatusError) as e:
        print(f"Aviso: O serviço de chatbot não respondeu à desconexão, mas o status será atualizado. Erro: {e}")

    chatbot_config = db.query(models.StoreChatbotConfig).filter_by(store_id=store.id).first()
    if chatbot_config:
        chatbot_config.connection_status = 'disconnected'
        chatbot_config.whatsapp_name = None
        chatbot_config.whatsapp_number = None
        chatbot_config.last_qr_code = None
        db.commit()
        await admin_emit_store_updated(db, store.id)

    return {"message": "Solicitação de desconexão processada com sucesso."}