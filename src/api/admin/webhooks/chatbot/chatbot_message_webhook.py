# src/api/webhooks/chatbot_message_webhook.py - VERSÃO CORRIGIDA
from fastapi import APIRouter, Depends, UploadFile, File, Form, HTTPException, BackgroundTasks
from src.core.database import GetDBDep
from src.core import models
from datetime import datetime, timezone
from .chatbot_webhook import verify_webhook_secret
from src.api.admin.socketio.emitters import emit_new_chat_message
from ...services.chatbot.secure_media_service import media_service

router = APIRouter(prefix="/webhooks", tags=["Webhooks"])


@router.post(
    "/chatbot/new-message",
    summary="Webhook para receber novas mensagens do chatbot",
    dependencies=[Depends(verify_webhook_secret)]
)
async def new_chatbot_message_webhook(
        background_tasks: BackgroundTasks,
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
    # ✅ 1. Validação de entrada
    if not store_id or store_id <= 0:
        raise HTTPException(422, "store_id inválido")

    if not chat_id or '@' not in chat_id:
        raise HTTPException(422, "chat_id inválido")

    # ✅ 2. Verificar duplicidade
    existing = db.query(models.ChatbotMessage).filter_by(message_uid=message_uid).first()
    if existing:
        return {"status": "sucesso", "message": "Mensagem duplicada"}

    # ✅ 3. Processar mídia em background (se existir)
    media_url = None
    if media_file and media_file.filename:
        try:
            media_url = await media_service.process_upload(media_file, store_id)
            if not media_url:
                print(f"⚠️ Upload de mídia falhou para {message_uid}")
        except Exception as e:
            print(f"❌ Erro no processamento de mídia: {e}")

    # ✅ 4. Converter timestamp
    try:
        message_timestamp = datetime.fromtimestamp(timestamp, tz=timezone.utc)
    except (ValueError, OSError):
        message_timestamp = datetime.now(timezone.utc)

    # ✅ 5. Criar mensagem
    new_message = models.ChatbotMessage(
        store_id=store_id,
        message_uid=message_uid,
        chat_id=chat_id,
        sender_id=sender_id,
        content_type=content_type,
        text_content=text_content,
        media_url=media_url,
        media_mime_type=media_mimetype_override or (media_file.content_type if media_file else None),
        is_from_me=is_from_me,
        timestamp=message_timestamp
    )

    try:
        db.add(new_message)
        db.commit()
        db.refresh(new_message)

        # ✅ 6. Emitir socket em background
        background_tasks.add_task(emit_new_chat_message, db, new_message)

        # ✅ 7. Atualizar metadados em background
        background_tasks.add_task(update_conversation_metadata, db, store_id, chat_id,
                                  text_content, message_timestamp, customer_name, is_from_me)

        return {"status": "sucesso", "message": "Mensagem processada"}

    except Exception as e:
        db.rollback()
        print(f"❌ Erro ao salvar mensagem: {e}")
        raise HTTPException(500, "Erro interno ao processar mensagem")


async def update_conversation_metadata(db: GetDBDep, store_id: int, chat_id: str,
                                       text_content: str, timestamp: datetime,
                                       customer_name: str, is_from_me: bool):
    """Atualiza metadados da conversação de forma assíncrona"""
    try:
        metadata = db.query(models.ChatbotConversationMetadata).filter_by(
            chat_id=chat_id, store_id=store_id
        ).first()

        if not metadata:
            metadata = models.ChatbotConversationMetadata(
                chat_id=chat_id,
                store_id=store_id,
                unread_count=0,
                customer_name=customer_name
            )
            db.add(metadata)

        # Atualizar campos
        preview = text_content or "(Mídia)"
        metadata.last_message_preview = preview[:100]  # Limitar tamanho
        metadata.last_message_timestamp = timestamp

        if not is_from_me:
            metadata.unread_count = (metadata.unread_count or 0) + 1
            metadata.customer_name = customer_name

        db.commit()

    except Exception as e:
        print(f"❌ Erro ao atualizar metadados: {e}")
        db.rollback()