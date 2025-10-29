# src/api/webhooks/chatbot_message_webhook.py

from fastapi import APIRouter, Depends, UploadFile, File, Form, HTTPException
from src.core.database import GetDBDep
from src.core import models
from datetime import datetime, timezone

# Importa o verify_webhook_secret corrigido do outro arquivo
from .chatbot_webhook import verify_webhook_secret

from src.api.admin.socketio.emitters import emit_new_chat_message
from ...services.chatbot.chatbot_media_service import upload_media_from_buffer
from ...services.chatbot.chatbot_profile_service import fetch_and_update_profile

router = APIRouter(prefix="/webhooks", tags=["Webhooks"])


@router.post(
    "/chatbot/new-message",
    summary="Webhook para receber novas mensagens (texto e mídia) do serviço de Chatbot",
    dependencies=[Depends(verify_webhook_secret)]
)
async def new_chatbot_message_webhook(
        db: GetDBDep,
        store_id: int = Form(...),
        chat_id: str = Form(...),
        sender_id: str = Form(...),
        message_uid: str = Form(...),
        content_type: str = Form(...),
        is_from_me: bool = Form(...),
        timestamp: int = Form(...),
        text_content: str = Form(None),
        media_file: UploadFile = File(None),
        customer_name: str = Form("Cliente"),
        media_filename_override: str = Form(None),
        media_mimetype_override: str = Form(None)
):
    # --- 1. Verificar Duplicidade (Idempotência) ---
    exists = db.query(models.ChatbotMessage).filter_by(message_uid=message_uid).first()  #
    if exists:
        return {"status": "sucesso", "message": "Mensagem duplicada, ignorada."}

    # --- 2. Processar Mídia (se existir) ---
    media_url = None
    media_mime_type = None

    if media_file:
        final_filename = media_filename_override or media_file.filename  #
        final_mimetype = media_mimetype_override or media_file.content_type  #

        file_bytes = await media_file.read()  #
        media_url = upload_media_from_buffer(
            store_id=store_id,
            file_buffer=file_bytes,
            filename=final_filename,
            content_type=final_mimetype
        )
        media_mime_type = final_mimetype  #

    message_timestamp = datetime.fromtimestamp(timestamp, tz=timezone.utc)

    # --- 3. Atualizar Metadados (Lógica ORM Otimizada) ---

    # Busca os metadados existentes
    metadata = db.query(models.ChatbotConversationMetadata).filter_by(
        chat_id=chat_id, store_id=store_id
    ).first()

    is_new_conversation = metadata is None

    if is_new_conversation:
        # Se for a primeira mensagem, cria os metadados
        metadata = models.ChatbotConversationMetadata(
            chat_id=chat_id,
            store_id=store_id,
            unread_count=0
        )
        db.add(metadata)
        # Tenta buscar a foto de perfil em segundo plano
        print(f"INFO: Nova conversa detectada para {chat_id}. Tentando buscar foto de perfil.")
        await fetch_and_update_profile(db=db, store_id=store_id, chat_id=chat_id)

    # Atualiza os campos dos metadados
    metadata.last_message_preview = text_content or f"({content_type.capitalize()})"
    metadata.last_message_timestamp = message_timestamp

    if not is_from_me:
        # Se a mensagem veio do cliente:
        # 1. Incrementa o contador de não lidas
        # 2. Atualiza o nome do cliente (pois o payload do cliente é a fonte mais recente)
        metadata.unread_count = (metadata.unread_count or 0) + 1
        metadata.customer_name = customer_name  #

    # --- 4. Salvar a Mensagem no Banco ---
    new_message = models.ChatbotMessage(
        store_id=store_id,
        message_uid=message_uid,
        chat_id=chat_id,
        sender_id=sender_id,
        content_type=content_type,
        text_content=text_content,
        media_url=media_url,
        media_mime_type=media_mime_type,
        is_from_me=is_from_me,
        timestamp=message_timestamp  #
    )

    db.add(new_message)

    # --- 5. Commit e Emissão do Socket ---
    try:
        db.commit()
        db.refresh(new_message)

        # Emite para o frontend (Socket.IO)
        await emit_new_chat_message(db, new_message)
    except Exception as e:
        db.rollback()
        print(f"ERRO ao salvar mensagem ou metadados: {e}")
        raise HTTPException(status_code=500, detail="Erro ao processar a mensagem.")

    return {"status": "sucesso", "message": "Mensagem processada."}

