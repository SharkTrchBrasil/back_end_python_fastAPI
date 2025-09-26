# src/core/services/chatbot_media_service.py

from typing import Optional
from src.core.aws import s3_client, AWS_BUCKET_NAME, logger
import uuid
import io


def _generate_media_key(store_id: int, original_filename: str) -> str:
    """ Gera uma chave única e organizada para o arquivo no S3. """
    ext = original_filename.split('.')[-1] if '.' in original_filename else 'bin'
    # Ex: chatbot/store_5/audio/abc-123.ogg
    return f"chatbot/store_{store_id}/{uuid.uuid4()}.{ext}"


def upload_media_from_buffer(
        store_id: int,
        file_buffer: bytes,
        filename: str,
        content_type: str
) -> Optional[str]:
    """
    Faz o upload de um buffer de bytes para o S3.

    Retorna a URL pública do arquivo se o upload for bem-sucedido.
    """
    if not s3_client or not AWS_BUCKET_NAME:
        logger.error("Upload de mídia cancelado: Cliente S3 não inicializado.")
        return None

    file_key = _generate_media_key(store_id, filename)

    try:
        # Usamos um buffer em memória (io.BytesIO) para o upload
        buffer = io.BytesIO(file_buffer)

        s3_client.upload_fileobj(
            buffer,
            AWS_BUCKET_NAME,
            file_key,
            ExtraArgs={'ContentType': content_type}
        )

        # Constrói a URL pública final
        public_url = f"https://{AWS_BUCKET_NAME}.s3.amazonaws.com/{file_key}"
        logger.info(f"✅ Mídia enviada com sucesso para: {public_url}")
        return public_url
    except Exception as e:
        logger.error(f"🚨 FALHA no upload de mídia para a chave '{file_key}'. Erro: {e}", exc_info=True)
        return None