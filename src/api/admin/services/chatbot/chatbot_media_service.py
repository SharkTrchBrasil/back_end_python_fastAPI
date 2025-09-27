# src/core/services/chatbot_media_service.py

from typing import Optional
from src.core.aws import s3_client, AWS_BUCKET_NAME, logger
import uuid
import io


# ✅ 1. NOVO HELPER PARA MAPEAR O TIPO DE CONTEÚDO PARA UMA EXTENSÃO DE ARQUIVO
def _get_extension_from_mimetype(content_type: Optional[str]) -> str:
    """ Mapeia um MIME type para uma extensão de arquivo comum. """
    if not content_type:
        return 'bin'

    mime_map = {
        'image/jpeg': 'jpg',
        'image/png': 'png',
        'image/gif': 'gif',
        'audio/ogg': 'ogg',
        'audio/mp4': 'm4a',
        'audio/mpeg': 'mp3',
        'application/pdf': 'pdf',
    }
    # Retorna a extensão correspondente ou '.bin' se não for encontrada
    return mime_map.get(content_type.lower(), 'bin')


# ✅ 2. FUNÇÃO ATUALIZADA PARA USAR O NOVO HELPER
def _generate_media_key(store_id: int, content_type: str) -> str:
    """ Gera uma chave única e organizada para o arquivo no S3 usando o content_type. """
    ext = _get_extension_from_mimetype(content_type)
    # A estrutura do nome do arquivo agora usa a extensão correta
    return f"chatbot/store_{store_id}/{uuid.uuid4()}.{ext}"


# ✅ 3. FUNÇÃO PRINCIPAL ATUALIZADA
def upload_media_from_buffer(
        store_id: int,
        file_buffer: bytes,
        filename: str,  # Mantemos o filename para logs, mas não para a extensão
        content_type: str
) -> Optional[str]:
    """
    Faz o upload de um buffer de bytes para o S3.
    Retorna a URL pública do arquivo se o upload for bem-sucedido.
    """
    if not s3_client or not AWS_BUCKET_NAME:
        logger.error("Upload de mídia cancelado: Cliente S3 não inicializado.")
        return None

    # A chave do arquivo agora é gerada com base no tipo de conteúdo, não no nome
    file_key = _generate_media_key(store_id, content_type)

    try:
        buffer = io.BytesIO(file_buffer)

        s3_client.upload_fileobj(
            buffer,
            AWS_BUCKET_NAME,
            file_key,
            ExtraArgs={'ContentType': content_type}
        )

        public_url = f"https://{AWS_BUCKET_NAME}.s3.amazonaws.com/{file_key}"
        logger.info(f"✅ Mídia '{filename}' enviada com sucesso para: {public_url}")
        return public_url
    except Exception as e:
        logger.error(f"🚨 FALHA no upload de mídia para a chave '{file_key}'. Erro: {e}", exc_info=True)
        return None