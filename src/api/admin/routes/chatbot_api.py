# src/api/admin/routers/chatbot_api.py - VERSÃO FINAL COMPLETA

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, BackgroundTasks
from sqlalchemy import desc
from typing import List

from src.api.admin.services.chatbot.chatbot_client import chatbot_client
from src.api.admin.services.chatbot.secure_media_service import media_service
from src.api.schemas.chatbot.chatbot_conversation import ChatbotConversationSchema
from src.api.schemas.chatbot.chatbot_message import ChatPanelInitialStateSchema
from src.core.utils.enums import OrderStatus
from src.core.database import GetDBDep
from src.core import models
from src.core.dependencies import GetStoreDep

router = APIRouter(tags=["Chatbot API"], prefix="/stores/{store_id}/chatbot")


@router.get("/conversations/{chat_id}", response_model=ChatPanelInitialStateSchema)
def get_conversation_history(
        chat_id: str,
        store: GetStoreDep,
        db: GetDBDep,
        skip: int = 0,
        limit: int = 50
):
    """
    Obtém histórico de conversa e pedido ativo do cliente
    """
    # ✅ 1. Buscar histórico de mensagens
    messages = db.query(models.ChatbotMessage) \
        .filter(
        models.ChatbotMessage.store_id == store.id,
        models.ChatbotMessage.chat_id == chat_id
    ) \
        .order_by(desc(models.ChatbotMessage.timestamp)) \
        .offset(skip) \
        .limit(limit) \
        .all()

    # ✅ 2. Buscar pedido ativo mais recente do cliente
    customer_phone = chat_id.split('@')[0]
    active_statuses = [
        OrderStatus.PENDING,
        OrderStatus.PREPARING,
        OrderStatus.READY,
        OrderStatus.ON_ROUTE
    ]

    recent_active_order = db.query(models.Order) \
        .filter(
        models.Order.store_id == store.id,
        # Busca flexível por número de telefone
        models.Order.customer_phone.like(f"%{customer_phone[-10:]}"),
        models.Order.order_status.in_(active_statuses)
    ) \
        .order_by(desc(models.Order.created_at)) \
        .first()

    # ✅ 3. Retornar payload combinado
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
    """
    Envia mensagem através do painel administrativo
    """
    # ✅ Extrair dados do payload
    chat_id = payload.get("chat_id")
    text_content = payload.get("text_content", "")
    media_url = payload.get("media_url")
    media_type = payload.get("media_type")
    media_filename = payload.get("media_filename")

    # ✅ Validação
    if not chat_id:
        raise HTTPException(
            status_code=400,
            detail="chat_id é obrigatório"
        )

    if not text_content and not media_url:
        raise HTTPException(
            status_code=400,
            detail="Pelo menos texto ou mídia é obrigatório"
        )

    # ✅ Enviar mensagem via chatbot client
    success = await chatbot_client.send_message(
        store_id=store.id,
        number=chat_id.split('@')[0],  # Extrai número do chat_id
        message=text_content,
        media_url=media_url,
        media_type=media_type
    )

    if not success:
        raise HTTPException(
            status_code=503,
            detail="Não foi possível enviar a mensagem pelo serviço de chatbot"
        )

    # ✅ Pausar chatbot para esta conversa
    pause_success = await chatbot_client.pause_chat(store.id, chat_id)
    if not pause_success:
        print(f"⚠️ Mensagem enviada, mas falha ao pausar chatbot para {chat_id}")

    return {
        "status": "sucesso",
        "message": "Mensagem enviada e bot pausado para esta conversa"
    }


@router.get("/conversations", response_model=List[ChatbotConversationSchema])
def get_conversations(
        store: GetStoreDep,
        db: GetDBDep,
        skip: int = 0,
        limit: int = 50
):
    """
    Lista todas as conversas da loja
    """
    conversations = db.query(models.ChatbotConversationMetadata) \
        .filter_by(store_id=store.id) \
        .order_by(desc(models.ChatbotConversationMetadata.last_message_timestamp)) \
        .offset(skip) \
        .limit(limit) \
        .all()

    return conversations


@router.post("/conversations/{chat_id}/mark-as-read", status_code=204)
def mark_conversation_as_read(
        chat_id: str,
        store: GetStoreDep,
        db: GetDBDep
):
    """
    Marca conversa como lida
    """
    conversation = db.query(models.ChatbotConversationMetadata) \
        .filter_by(store_id=store.id, chat_id=chat_id) \
        .first()

    if conversation and conversation.unread_count > 0:
        conversation.unread_count = 0
        db.commit()

    return None


@router.post("/upload-media", summary="Faz o upload de um arquivo de mídia para o S3")
async def upload_media(
        store: GetStoreDep,
        media_file: UploadFile = File(...),
        background_tasks: BackgroundTasks = None
):
    """
    Upload seguro de arquivos de mídia
    """
    if not media_file:
        raise HTTPException(status_code=400, detail="Nenhum arquivo enviado.")

    try:
        # ✅ Usar o serviço seguro de mídia
        media_url = await media_service.process_upload(media_file, store.id)

        if not media_url:
            raise HTTPException(
                status_code=500,
                detail="Falha no upload da mídia para o S3"
            )

        return {"media_url": media_url}

    except Exception as e:
        print(f"❌ Erro no upload de mídia: {e}")
        raise HTTPException(
            status_code=500,
            detail="Erro interno no processamento do arquivo"
        )


# ✅ NOVA ROTA PARA BUSCAR INFORMAÇÕES DO CONTATO
@router.get("/conversations/{chat_id}/contact-info")
async def get_contact_info(
        chat_id: str,
        store: GetStoreDep,
        db: GetDBDep
):
    """
    Busca informações do contato (nome e foto de perfil)
    """
    # ✅ Buscar metadados existentes
    metadata = db.query(models.ChatbotConversationMetadata) \
        .filter_by(store_id=store.id, chat_id=chat_id) \
        .first()

    contact_name = None
    profile_pic_url = None

    if metadata:
        contact_name = metadata.customer_name
        profile_pic_url = metadata.customer_profile_pic_url

    # ✅ Se não tem nome, tentar buscar do WhatsApp
    if not contact_name:
        contact_name = await chatbot_client.get_contact_name(store.id, chat_id)

        # ✅ Atualizar no banco se encontrou
        if contact_name and metadata:
            metadata.customer_name = contact_name
            db.commit()

    # ✅ Se não tem foto, tentar buscar do WhatsApp
    if not profile_pic_url:
        profile_pic_url = await chatbot_client.get_profile_picture(store.id, chat_id)

        # ✅ Atualizar no banco se encontrou
        if profile_pic_url and metadata:
            metadata.customer_profile_pic_url = profile_pic_url
            db.commit()

    return {
        "contact_name": contact_name,
        "profile_pic_url": profile_pic_url,
        "chat_id": chat_id
    }