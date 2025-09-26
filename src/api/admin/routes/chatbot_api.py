# src/api/admin/routers/chatbot_api.py

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import desc
from typing import List

from src.api.admin.services.chatbot.chatbot_sender_service import send_whatsapp_message
from src.api.schemas.chatbot.chatbot_message import ChatPanelInitialStateSchema
# ✅ 1. IMPORTAR OS NOVOS SCHEMAS E UTILITÁRIOS

from src.core.utils.enums import OrderStatus # Para filtrar pelos status de pedido

from src.core.database import GetDBDep
from src.core import models
from src.core.dependencies import GetStoreDep


router = APIRouter(tags=["Chatbot API"], prefix="/stores/{store_id}/chatbot")

# ✅ 2. ATUALIZAR A FUNÇÃO PARA USAR O NOVO RESPONSE_MODEL E ADICIONAR A LÓGICA
@router.get("/conversations/{chat_id}", response_model=ChatPanelInitialStateSchema)
def get_conversation_history(
    chat_id: str,
    store: GetStoreDep,
    db: GetDBDep,
    skip: int = 0,
    limit: int = 50
):
    # --- Parte 1: Busca o histórico de mensagens (lógica que já tínhamos) ---
    messages = db.query(models.ChatbotMessage) \
        .filter(models.ChatbotMessage.store_id == store.id, models.ChatbotMessage.chat_id == chat_id) \
        .order_by(desc(models.ChatbotMessage.timestamp)) \
        .offset(skip) \
        .limit(limit) \
        .all()

    # --- Parte 2: Busca o pedido ativo mais recente do cliente ---
    customer_phone = chat_id.split('@')[0]
    active_statuses = [OrderStatus.PENDING, OrderStatus.PREPARING, OrderStatus.READY, OrderStatus.ON_ROUTE]

    recent_active_order = db.query(models.Order)\
        .filter(
            models.Order.store_id == store.id,
            # Busca por números que terminam com os dígitos do cliente para maior flexibilidade
            models.Order.customer_phone.like(f"%{customer_phone[-10:]}"),
            models.Order.order_status.in_(active_statuses)
        )\
        .order_by(desc(models.Order.created_at))\
        .first()

    # --- Parte 3: Retorna o payload combinado usando o novo schema ---
    return ChatPanelInitialStateSchema(
        messages=messages,
        active_order=recent_active_order
    )


@router.post("/conversations/send-message")
async def send_message_from_panel(
    payload: dict,
    store: GetStoreDep,
    db: GetDBDep
):
    # (Esta função permanece exatamente como está)
    chat_id = payload.get("chat_id")
    text_content = payload.get("text_content")

    if not all([chat_id, text_content]):
        raise HTTPException(status_code=400, detail="Dados incompletos. 'chat_id' e 'text_content' são obrigatórios.")

    success = await send_whatsapp_message(store.id, chat_id, text_content)

    if not success:
        raise HTTPException(status_code=503, detail="Não foi possível enviar a mensagem pelo serviço de chatbot.")

    return {"status": "sucesso", "message": "Mensagem enviada para a fila de envio."}