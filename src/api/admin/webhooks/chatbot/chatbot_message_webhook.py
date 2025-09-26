# src/api/webhooks/chatbot_message_webhook.py

from fastapi import APIRouter, Depends, Header, HTTPException, UploadFile, File, Form
from src.core.database import GetDBDep
from src.core import models



from datetime import datetime, timezone

# Importe e verifique o secret como no outro webhook
from .chatbot_webhook import verify_webhook_secret
from ...services.chatbot.chatbot_media_service import upload_media_from_buffer
from ...socketio.emitters import emit_new_chat_message

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
        media_file: UploadFile = File(None)
):
    # Verifica se a mensagem já existe para evitar duplicatas
    exists = db.query(models.ChatbotMessage).filter_by(message_uid=message_uid).first()
    if exists:
        return {"status": "sucesso", "message": "Mensagem duplicada, ignorada."}

    media_url = None
    media_mime_type = None

    # Se for um arquivo de mídia, faz o upload para o S3
    if media_file:
        file_bytes = await media_file.read()
        media_url = upload_media_from_buffer(
            store_id=store_id,
            file_buffer=file_bytes,
            filename=media_file.filename,
            content_type=media_file.content_type
        )
        media_mime_type = media_file.content_type

    # Cria o novo registro da mensagem no banco
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
        timestamp=datetime.fromtimestamp(timestamp, tz=timezone.utc)
    )

    db.add(new_message)
    db.commit()
    db.refresh(new_message)  # Para pegar o ID gerado

    # Notifica o frontend (Flutter) em tempo real via WebSocket
    await emit_new_chat_message(db, new_message)

    return {"status": "sucesso", "message": "Mensagem processada."}