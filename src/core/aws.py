import boto3
import uuid
import os
from botocore.client import BaseClient
from typing import Optional

import boto3
import uuid
import os
from botocore.client import BaseClient
from typing import Optional

# Lê as variáveis de ambiente
AWS_ACCESS_KEY_ID = os.getenv("AWS_ACCESS_KEY_ID")
AWS_SECRET_ACCESS_KEY = os.getenv("AWS_SECRET_ACCESS_KEY")
AWS_REGION = os.getenv("AWS_REGION")
AWS_BUCKET_NAME = os.getenv("AWS_BUCKET_NAME")


S3_PUBLIC_BASE_URL = f"https://{AWS_BUCKET_NAME}.s3.{AWS_REGION}.amazonaws.com"

# A criação do cliente continua a mesma
s3_client: BaseClient = boto3.client(
    's3',
    aws_access_key_id=AWS_ACCESS_KEY_ID,
    aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
    region_name=AWS_REGION
)


# ✅ 2. ATUALIZA A FUNÇÃO DE UPLOAD
def upload_file(file) -> str:
    """
    Faz o upload de um arquivo para o S3 e o torna publicamente legível.
    """
    file_key = f"{uuid.uuid4()}_{file.filename}"

    # Adicionamos `ExtraArgs` para definir a permissão do arquivo no momento do upload.
    s3_client.upload_fileobj(
        file.file,
        AWS_BUCKET_NAME,
        file_key,
        ExtraArgs={'ACL': 'public-read'}  # <-- A MÁGICA ESTÁ AQUI
    )
    return file_key



def get_presigned_url(file_key: Optional[str]) -> Optional[str]:
    if file_key:
        try:
            pre_signed_url = s3_client.generate_presigned_url(
                'get_object',
                Params={'Bucket': AWS_BUCKET_NAME, 'Key': file_key},
                ExpiresIn=86400  # 24 hours (60 * 60 * 24)
            )
            return pre_signed_url
        except Exception as e:
            print(f"Erro ao gerar URL pré-assinada para {file_key}: {e}")
            return None
    return None


def delete_file(file_key: Optional[str]) -> None:
    # Adicionamos uma verificação para não dar erro se a chave for nula
    if file_key:
        s3_client.delete_object(Bucket=AWS_BUCKET_NAME, Key=file_key)








