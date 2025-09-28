# src/api/webhooks/chatbot_message_webhook.py

from fastapi import APIRouter, Depends, UploadFile, File, Form
from src.core.database import GetDBDep
from src.core import models
from datetime import datetime, timezone
from sqlalchemy import table, column
from sqlalchemy.dialects.postgresql import insert as pg_insert

# Importe e verifique o secret como no outro webhook
from .chatbot_webhook import verify_webhook_secret


from src.api.admin.socketio.emitters import emit_new_chat_message
from ...services.chatbot.chatbot_media_service import upload_media_from_buffer
from ...services.chatbot.chatbot_profile_service import fetch_and_update_profile, fetch_contact_name

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
        # ✅ 1. RECEBE OS NOVOS CAMPOS ENVIADOS PELO NODE.JS
        media_filename_override: str = Form(None),
        media_mimetype_override: str = Form(None)
):
    # O resto da sua lógica, que já estava correta, permanece igual.

    # Verifica duplicatas
    exists = db.query(models.ChatbotMessage).filter_by(message_uid=message_uid).first()
    if exists:
        return {"status": "sucesso", "message": "Mensagem duplicada, ignorada."}

    # ✅ 2. LÓGICA ATUALIZADA
    final_customer_name = customer_name

    existing_metadata = db.query(models.ChatbotConversationMetadata).filter_by(
        chat_id=chat_id, store_id=store_id
    ).first()
    is_new_conversation = existing_metadata is None
    # ✅ --- FIM DA ALTERAÇÃO ---


    # Se a mensagem é da loja E a conversa ainda não existe, busca o nome
    if is_from_me and not existing_metadata:
        fetched_name = await fetch_contact_name(store_id, chat_id)
        if fetched_name:
            final_customer_name = fetched_name



    media_url = None
    media_mime_type = None

    # Lida com a mídia
    if media_file:
        # ✅ 2. USA OS NOVOS CAMPOS COMO FONTE DA VERDADE
        final_filename = media_filename_override or media_file.filename
        final_mimetype = media_mimetype_override or media_file.content_type

        print(f"--- DEBUG PYTHON FINAL ---")
        print(f"Filename a ser usado: {final_filename}")
        print(f"Mimetype a ser usado: {final_mimetype}")

        file_bytes = await media_file.read()
        media_url = upload_media_from_buffer(
            store_id=store_id,
            file_buffer=file_bytes,
            filename=final_filename,
            content_type=final_mimetype # Passa o mimetype correto para o serviço de upload
        )
        media_mime_type = final_mimetype # Guarda o mimetype correto no banco


    # Atualiza metadados da conversa
    metadata_table = table('chatbot_conversation_metadata',
                           column('chat_id'), column('store_id'),
                           column('unread_count'), column('customer_name'),
                           column('last_message_preview'), column('last_message_timestamp'))
    values_to_insert = {
        'chat_id': chat_id, 'store_id': store_id, 'customer_name': customer_name,
        'last_message_preview': text_content or f"({content_type.capitalize()})",
        'last_message_timestamp': datetime.fromtimestamp(timestamp, tz=timezone.utc),
        'unread_count': 1 if not is_from_me else 0
    }
    stmt = pg_insert(models.ChatbotConversationMetadata).values(values_to_insert)


    update_dict = {
        'last_message_preview': stmt.excluded.last_message_preview,
        'last_message_timestamp': stmt.excluded.last_message_timestamp,
        'unread_count': metadata_table.c.unread_count + (1 if not is_from_me else 0)
    }
    if not is_from_me:
        # Só atualiza o nome do cliente se a mensagem veio dele
        update_dict['customer_name'] = final_customer_name

    stmt = stmt.on_conflict_do_update(
        index_elements=['chat_id', 'store_id'],
        set_=update_dict
    )


    db.execute(stmt)

    # Cria a nova mensagem
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


    # ✅ --- INÍCIO DA ALTERAÇÃO ---
    # 2. Agora, só chamamos a função se a conversa for realmente nova.
    if is_new_conversation:
        print(f"INFO: Nova conversa detectada para {chat_id}. Tentando buscar foto de perfil.")
        await fetch_and_update_profile(db=db, store_id=store_id, chat_id=chat_id)
    # ✅ --- FIM DA ALTERAÇÃO ---


    # Notifica o frontend
    await emit_new_chat_message(db, new_message)

    return {"status": "sucesso", "message": "Mensagem processada."}