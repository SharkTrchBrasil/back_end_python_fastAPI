# src/api/webhooks/chatbot_message_webhook.py

from fastapi import APIRouter, Depends, Header, HTTPException, UploadFile, File, Form
# ❌ REMOVIDO: A importação do numpy não era necessária
from src.core.database import GetDBDep
from src.core import models
from datetime import datetime, timezone

# Importe e verifique o secret como no outro webhook
from .chatbot_webhook import verify_webhook_secret
# ✅ CORREÇÃO: Ajustei o caminho do import para o padrão dos seus outros arquivos
from sqlalchemy import table, column

from src.api.admin.socketio.emitters import emit_new_chat_message

from sqlalchemy.dialects.postgresql import insert as pg_insert

from ...services.chatbot.chatbot_media_service import upload_media_from_buffer

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
        # ✅ CORREÇÃO 1: Adicionado 'customer_name' como um parâmetro do formulário
        customer_name: str = Form("Cliente")
):
    # Verifica se a mensagem já existe para evitar duplicatas (correto)
    exists = db.query(models.ChatbotMessage).filter_by(message_uid=message_uid).first()
    if exists:
        return {"status": "sucesso", "message": "Mensagem duplicada, ignorada."}

    media_url = None
    media_mime_type = None

    # Se for um arquivo de mídia, faz o upload para o S3 (correto)
    if media_file:
        file_bytes = await media_file.read()
        media_url = upload_media_from_buffer(
            store_id=store_id,
            file_buffer=file_bytes,
            filename=media_file.filename,
            content_type=media_file.content_type
        )
        media_mime_type = media_file.content_type

    metadata_table = table('chatbot_conversation_metadata',
                           column('chat_id'),
                           column('store_id'),
                           column('unread_count'),
                           # Adicione outras colunas que você atualiza
                           column('customer_name'),
                           column('last_message_preview'),
                           column('last_message_timestamp')
                           )

    values_to_insert = {
        'chat_id': chat_id,
        'store_id': store_id,
        'customer_name': customer_name,
        'last_message_preview': text_content or f"({content_type.capitalize()})",
        'last_message_timestamp': datetime.fromtimestamp(timestamp, tz=timezone.utc),
        'unread_count': 1 if not is_from_me else 0  # Valor inicial se for uma nova conversa
    }

    stmt = pg_insert(models.ChatbotConversationMetadata).values(values_to_insert)

    stmt = stmt.on_conflict_do_update(
        index_elements=['chat_id', 'store_id'],
        set_={
            'customer_name': stmt.excluded.customer_name,
            'last_message_preview': stmt.excluded.last_message_preview,
            'last_message_timestamp': stmt.excluded.last_message_timestamp,
            # A mágica está aqui:
            # Pega o valor atual da coluna 'unread_count' na tabela
            # e soma 1 (ou 0 se a mensagem for da loja).
            'unread_count': metadata_table.c.unread_count + (1 if not is_from_me else 0)
        }
    )
    db.execute(stmt)

    # ✅ CORREÇÃO 2: Criando o objeto da nova mensagem antes de salvá-lo
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
    db.refresh(new_message)

    # Notifica o frontend (Flutter) em tempo real via WebSocket (correto)
    await emit_new_chat_message(db, new_message)

    return {"status": "sucesso", "message": "Mensagem processada."}