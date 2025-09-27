# src/core/services/chatbot_media_service.py

from typing import Optional
from src.core.aws import s3_client, AWS_BUCKET_NAME, logger
import uuid
import io


# DEPOIS (Versão Corrigida):
def _get_extension_from_mimetype(content_type: Optional[str]) -> str:
    """ Mapeia um MIME type para uma extensão de arquivo comum,
        limpando informações extras como codecs. """
    if not content_type:
        return 'bin'

    # ✅ A MUDANÇA CRÍTICA ESTÁ AQUI:
    # Pega a parte principal do content-type antes de qualquer ';'
    clean_content_type = content_type.split(';')[0].strip().lower()

    mime_map = {
        'image/jpeg': 'jpg',
        'image/jpg': 'jpg',
        'image/png': 'png',
        'image/gif': 'gif',
        'image/webp': 'webp',
        'audio/ogg': 'ogg',
        'audio/mp4': 'm4a',
        'audio/mpeg': 'mp3',
        'application/pdf': 'pdf',
        'video/mp4': 'mp4',
        'video/quicktime': 'mov'
    }

    # Agora a busca será feita com o tipo limpo (ex: 'audio/ogg')
    return mime_map.get(clean_content_type, 'bin')



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