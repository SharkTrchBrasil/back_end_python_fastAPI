# src/core/services/chatbot_media_service.py - VERSÃO COMPLETA

from typing import Optional
import uuid
import io

# ✅ IMPORTAR CONFIGURAÇÕES DO AWS
try:
    from src.core.aws import s3_client, AWS_BUCKET_NAME, logger
except ImportError:
    # Fallback para desenvolvimento
    s3_client = None
    AWS_BUCKET_NAME = None
    import logging

    logger = logging.getLogger(__name__)


def _get_extension_from_mimetype(content_type: Optional[str]) -> str:
    """
    Mapeia um MIME type para uma extensão de arquivo comum,
    limpando informações extras como codecs.
    """
    if not content_type:
        return 'bin'

    # ✅ PRINT PARA DEPURAR (opcional - pode remover em produção)
    print(f"--- DEBUG PYTHON (MEDIA SERVICE) ---")
    print(f"Recebido content_type: '{content_type}'")

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
        'audio/wav': 'wav',
        'application/pdf': 'pdf',
        'video/mp4': 'mp4',
        'video/3gpp': '3gp',
        'video/quicktime': 'mov',
        'text/plain': 'txt'
    }

    # Agora a busca será feita com o tipo limpo (ex: 'audio/ogg')
    ext = mime_map.get(clean_content_type, 'bin')

    # ✅ PRINT PARA DEPURAR (opcional)
    print(f"Extensão retornada: '{ext}'")
    return ext


def _generate_media_key(store_id: int, content_type: str) -> str:
    """
    Gera uma chave única e organizada para o arquivo no S3 usando o content_type.
    """
    ext = _get_extension_from_mimetype(content_type)
    # A estrutura do nome do arquivo agora usa a extensão correta
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

    # ✅ Validações básicas
    if not file_buffer:
        logger.error("Upload de mídia cancelado: Buffer vazio.")
        return None

    if not content_type:
        logger.error("Upload de mídia cancelado: Content-Type não especificado.")
        return None

    # A chave do arquivo agora é gerada com base no tipo de conteúdo, não no nome
    file_key = _generate_media_key(store_id, content_type)

    try:
        buffer = io.BytesIO(file_buffer)

        # ✅ Configurações de upload baseadas no tipo de arquivo
        extra_args = {'ContentType': content_type}

        # ✅ Configurações específicas por tipo de arquivo
        if content_type.startswith('image/'):
            extra_args['ContentDisposition'] = 'inline'
        elif content_type.startswith('video/'):
            extra_args['ContentDisposition'] = 'attachment'
        elif content_type.startswith('audio/'):
            extra_args['ContentDisposition'] = 'attachment'

        s3_client.upload_fileobj(
            buffer,
            AWS_BUCKET_NAME,
            file_key,
            ExtraArgs=extra_args
        )

        public_url = f"https://{AWS_BUCKET_NAME}.s3.amazonaws.com/{file_key}"
        logger.info(f"✅ Mídia '{filename}' enviada com sucesso para: {public_url}")
        return public_url

    except Exception as e:
        logger.error(f"🚨 FALHA no upload de mídia para a chave '{file_key}'. Erro: {e}", exc_info=True)
        return None


# ✅ FUNÇÃO ADICIONAL PARA VALIDAR SE O AWS ESTÁ CONFIGURADO
def is_aws_configured() -> bool:
    """Verifica se o AWS S3 está configurado corretamente"""
    return s3_client is not None and AWS_BUCKET_NAME is not None


# ✅ FUNÇÃO PARA OBTER URL ASSINADA (OPCIONAL)
def get_signed_url(file_key: str, expiration: int = 3600) -> Optional[str]:
    """
    Gera uma URL assinada temporária para um arquivo no S3
    """
    if not is_aws_configured():
        return None

    try:
        url = s3_client.generate_presigned_url(
            'get_object',
            Params={
                'Bucket': AWS_BUCKET_NAME,
                'Key': file_key
            },
            ExpiresIn=expiration
        )
        return url
    except Exception as e:
        logger.error(f"Erro ao gerar URL assinada para {file_key}: {e}")
        return None