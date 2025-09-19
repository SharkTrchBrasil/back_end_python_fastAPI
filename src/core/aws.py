
import boto3
import uuid
import os
from botocore.client import BaseClient
from typing import Optional, List
from fastapi import UploadFile
from botocore.exceptions import BotoCoreError, ClientError  # ✅ Importe as exceções



print("--- 🏁 Carregando configurações da AWS ---")
AWS_ACCESS_KEY_ID = os.getenv("AWS_ACCESS_KEY_ID")
AWS_SECRET_ACCESS_KEY = os.getenv("AWS_SECRET_ACCESS_KEY")
AWS_REGION = os.getenv("AWS_REGION")
AWS_BUCKET_NAME = os.getenv("AWS_BUCKET_NAME")

print(f"AWS_ACCESS_KEY_ID: {'...' + AWS_ACCESS_KEY_ID[-4:] if AWS_ACCESS_KEY_ID else 'NÃO CARREGADO'}")
print(f"AWS_REGION: {AWS_REGION}")
print(f"AWS_BUCKET_NAME: {AWS_BUCKET_NAME}")
# Não imprima a chave secreta inteira por segurança

S3_PUBLIC_BASE_URL = f"https://{AWS_BUCKET_NAME}.s3.{AWS_REGION}.amazonaws.com"

try:
    s3_client: BaseClient = boto3.client(
        's3',
        aws_access_key_id=AWS_ACCESS_KEY_ID,
        aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
        region_name=AWS_REGION
    )
    print("✅ Cliente S3 Boto3 inicializado com sucesso.")
except Exception as e:
    s3_client = None
    print(f"🚨🚨🚨 FALHA ao inicializar o cliente S3 Boto3: {e}")


# --- Funções Refatoradas e Novas ---

def _generate_file_key(folder: str, filename: str) -> str:
    """Gera uma chave de arquivo única dentro de uma 'pasta'."""
    ext = filename.split('.')[-1] if '.' in filename else ''
    return f"{folder}/{uuid.uuid4()}.{ext}"


# ✅ FUNÇÃO COM LOG DE ERRO DETALHADO
def upload_single_file(file: UploadFile, folder: str = 'uploads') -> Optional[str]:
    """
    Faz o upload de UM arquivo para uma pasta específica no S3.
    Retorna a chave do arquivo ou None se o arquivo for nulo.
    """
    if not file or not file.filename:
        return None

    if not s3_client:
        print("🚨 Erro Crítico: Cliente S3 não foi inicializado. Upload cancelado.")
        return None

    file_key = _generate_file_key(folder, file.filename)

    try:
        s3_client.upload_fileobj(
            file.file,
            AWS_BUCKET_NAME,
            file_key,
            ExtraArgs={'ACL': 'public-read', 'ContentType': file.content_type}
        )
        # Este print só aparecerá se o upload der certo
        print(f"   ✅ Sucesso! Arquivo '{file.filename}' enviado para S3 com a chave: {file_key}")
        return file_key

    # ✅ CAPTURA E LOG DE ERROS ESPECÍFICOS
    except ClientError as e:
        error_code = e.response.get("Error", {}).get("Code")
        print(f"🚨🚨🚨 ERRO DO CLIENTE AWS (ClientError) ao fazer upload de '{file.filename}':")
        print(f"   -> Código do Erro: {error_code}")
        print(f"   -> Mensagem: {e}")
        return None
    except BotoCoreError as e:
        print(f"🚨🚨🚨 ERRO DO BOTOCORE (BotoCoreError) ao fazer upload de '{file.filename}': {e}")
        return None
    except Exception as e:
        print(f"🚨🚨🚨 ERRO INESPERADO GENÉRICO ao fazer upload de '{file.filename}': {e}")
        return None




def delete_file(file_key: Optional[str]) -> None:
    """Deleta UM arquivo do S3 pela sua chave."""
    if file_key:
        try:
            s3_client.delete_object(Bucket=AWS_BUCKET_NAME, Key=file_key)
            print(f"🗑️ Arquivo '{file_key}' deletado do S3.")
        except Exception as e:
            print(f"⚠️ Erro ao deletar o arquivo '{file_key}' do S3: {e}")


def delete_multiple_files(file_keys: List[str]) -> None:
    """Deleta MÚLTIPLOS arquivos do S3."""
    if not file_keys:
        return

    # O S3 permite deletar até 1000 objetos de uma vez
    objects_to_delete = [{'Key': key} for key in file_keys]

    try:
        s3_client.delete_objects(
            Bucket=AWS_BUCKET_NAME,
            Delete={'Objects': objects_to_delete}
        )
        print(f"🗑️ {len(file_keys)} arquivos deletados do S3.")
    except Exception as e:
        print(f"⚠️ Erro ao deletar múltiplos arquivos do S3: {e}")


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