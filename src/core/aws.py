import boto3
import uuid
import os
import logging
from typing import Optional, List
from fastapi import UploadFile
from botocore.exceptions import BotoCoreError, ClientError

# 1. Configuração do Logging (muito mais robusto que print)
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

logger.info("--- 🏁 Módulo AWS está sendo carregado ---")

# 2. Carregamento das Variáveis de Ambiente
AWS_ACCESS_KEY_ID = os.getenv("AWS_ACCESS_KEY_ID")
AWS_SECRET_ACCESS_KEY = os.getenv("AWS_SECRET_ACCESS_KEY")
AWS_REGION = os.getenv("AWS_REGION")
AWS_BUCKET_NAME = os.getenv("AWS_BUCKET_NAME")

logger.info(f"AWS_ACCESS_KEY_ID: {'...' + AWS_ACCESS_KEY_ID[-4:] if AWS_ACCESS_KEY_ID else 'NÃO CARREGADO'}")
logger.info(f"AWS_REGION: {AWS_REGION}")
logger.info(f"AWS_BUCKET_NAME: {AWS_BUCKET_NAME}")

S3_PUBLIC_BASE_URL = f"https://{AWS_BUCKET_NAME}.s3.{AWS_REGION}.amazonaws.com" if AWS_BUCKET_NAME and AWS_REGION else None
logger.info(f"S3_PUBLIC_BASE_URL: {S3_PUBLIC_BASE_URL}")

s3_client = None
try:
    s3_client = boto3.client(
        's3',
        aws_access_key_id=AWS_ACCESS_KEY_ID,
        aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
        region_name=AWS_REGION
    )
    logger.info("✅ Cliente S3 Boto3 inicializado com sucesso.")
except (BotoCoreError, ClientError) as e:
    logger.error(f"🚨🚨🚨 FALHA CRÍTICA ao inicializar o cliente S3 Boto3: {e}", exc_info=True)
except Exception as e:
    logger.error(f"🚨🚨🚨 ERRO INESPERADO ao inicializar o cliente S3: {e}", exc_info=True)


def _generate_file_key(folder: str, filename: str) -> str:
    ext = filename.split('.')[-1] if '.' in filename else ''
    return f"{folder}/{uuid.uuid4()}.{ext}"


def upload_single_file(file: UploadFile, folder: str = 'uploads') -> Optional[str]:
    logger.info(f"Iniciando tentativa de upload para o arquivo '{file.filename}' na pasta '{folder}'.")

    if not s3_client:
        logger.error("Upload cancelado: Cliente S3 não foi inicializado.")
        return None
    if not file or not file.filename or not AWS_BUCKET_NAME:
        logger.warning("Upload cancelado: Arquivo ou nome do arquivo ou nome do bucket ausente.")
        return None

    file_key = _generate_file_key(folder, file.filename)

    try:
        logger.info(f"Tentando fazer upload do arquivo para a chave S3: {file_key}")
        s3_client.upload_fileobj(
            file.file,
            AWS_BUCKET_NAME,
            file_key,
            ExtraArgs={'ACL': 'public-read', 'ContentType': file.content_type}
        )
        logger.info(f"✅ Upload para a chave '{file_key}' finalizado com sucesso!")
        return file_key
    except Exception as e:
        logger.error(f"🚨 FALHA no upload para a chave '{file_key}'. Erro: {e}", exc_info=True)
        return None


def delete_file(file_key: str):
    if not s3_client:
        logger.error("Delete cancelado: Cliente S3 não foi inicializado.")
        return
    try:
        s3_client.delete_object(Bucket=AWS_BUCKET_NAME, Key=file_key)
        logger.info(f"Arquivo '{file_key}' deletado com sucesso.")
    except Exception as e:
        logger.error(f"🚨 Erro ao deletar o arquivo '{file_key}': {e}", exc_info=True)


def delete_multiple_files(file_keys: List[str]):
    if not s3_client:
        logger.error("Delete em massa cancelado: Cliente S3 não foi inicializado.")
        return
    if not file_keys:
        return
    objects_to_delete = [{'Key': key} for key in file_keys]
    try:
        s3_client.delete_objects(Bucket=AWS_BUCKET_NAME, Delete={'Objects': objects_to_delete})
        logger.info(f"{len(file_keys)} arquivos deletados com sucesso.")
    except Exception as e:
        logger.error(f"🚨 Erro ao deletar múltiplos arquivos: {e}", exc_info=True)




# A função de URL pré-assinada continua a mesma, pois não a usaremos para conteúdo público
def get_presigned_url(file_key: Optional[str]) -> Optional[str]:
    # ... (código existente sem alteração) ...
    if file_key:
        try:
            pre_signed_url = s3_client.generate_presigned_url(
                'get_object',
                Params={'Bucket': AWS_BUCKET_NAME, 'Key': file_key},
                ExpiresIn=86400
            )
            return pre_signed_url
        except Exception as e:
            print(f"Erro ao gerar URL pré-assinada para {file_key}: {e}")
            return None
    return None