# Arquivo: src/core/aws.py (VERSÃO DE TESTE PARA FORÇAR O ERRO)

import boto3
import uuid
import os
from typing import Optional
from fastapi import UploadFile

# 1. VAMOS VERIFICAR AS VARIÁVEIS NOVAMENTE
print("--- 🏁 [TESTE RADICAL] Carregando configurações da AWS ---")
AWS_ACCESS_KEY_ID = os.getenv("AWS_ACCESS_KEY_ID")
AWS_SECRET_ACCESS_KEY = os.getenv("AWS_SECRET_ACCESS_KEY")
AWS_REGION = os.getenv("AWS_REGION")
AWS_BUCKET_NAME = os.getenv("AWS_BUCKET_NAME")

print(f"AWS_ACCESS_KEY_ID: {'...' + AWS_ACCESS_KEY_ID[-4:] if AWS_ACCESS_KEY_ID else 'NÃO CARREGADO'}")
print(f"AWS_SECRET_ACCESS_KEY: {'CARREGADA' if AWS_SECRET_ACCESS_KEY else 'NÃO CARREGADA'}")
print(f"AWS_REGION: {AWS_REGION}")
print(f"AWS_BUCKET_NAME: {AWS_BUCKET_NAME}")

# 2. INICIALIZAÇÃO DO CLIENTE SEM TRY/EXCEPT
# Se houver um problema com as credenciais, a aplicação vai quebrar AQUI.
s3_client = boto3.client(
    's3',
    aws_access_key_id=AWS_ACCESS_KEY_ID,
    aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
    region_name=AWS_REGION
)
print("✅ [TESTE RADICAL] Cliente S3 Boto3 aparentemente inicializado.")


def _generate_file_key(folder: str, filename: str) -> str:
    ext = filename.split('.')[-1] if '.' in filename else ''
    return f"{folder}/{uuid.uuid4()}.{ext}"


def upload_single_file(file: UploadFile, folder: str = 'uploads') -> Optional[str]:
    if not file or not file.filename:
        return None

    file_key = _generate_file_key(folder, file.filename)

    # 3. UPLOAD SEM TRY/EXCEPT
    # Se a inicialização passar mas o upload falhar, a aplicação vai quebrar AQUI.
    s3_client.upload_fileobj(
        file.file,
        AWS_BUCKET_NAME,
        file_key,
        ExtraArgs={'ACL': 'public-read', 'ContentType': file.content_type}
    )

    print(f"   ✅ [TESTE RADICAL] Sucesso! Arquivo '{file.filename}' enviado para S3 com a chave: {file_key}")
    return file_key


def delete_multiple_files(file_keys: list[str]):
    # Esta função não é o foco agora, mas a deixamos aqui
    if not file_keys:
        return
    objects_to_delete = [{'Key': key} for key in file_keys]
    try:
        s3_client.delete_objects(
            Bucket=AWS_BUCKET_NAME,
            Delete={'Objects': objects_to_delete}
        )
    except Exception as e:
        print(f"🚨 Erro ao deletar múltiplos arquivos do S3: {e}")



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