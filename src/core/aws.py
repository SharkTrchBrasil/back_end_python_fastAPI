import boto3
import uuid
import os
from botocore.client import BaseClient
from typing import Optional

# Assuming 'config' is an object or module you have defined
# that holds your AWS configuration.
AWS_ACCESS_KEY = os.getenv("AWS_ACCESS_KEY")
AWS_SECRET_KEY = os.getenv("AWS_SECRET_KEY")
AWS_REGION = os.getenv("AWS_REGION")
AWS_BUCKET_NAME = os.getenv("AWS_BUCKET_NAME")

s3_client: BaseClient = boto3.client(
    's3',
    aws_access_key_id=AWS_ACCESS_KEY,
    aws_secret_access_key=AWS_SECRET_KEY,
    region_name=AWS_REGION
)

def upload_file(file) -> str:
    file_key = f"{uuid.uuid4()}_{file.filename}"
    s3_client.upload_fileobj(file.file, AWS_BUCKET_NAME, file_key)
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

def delete_file(file_key: str) -> None:
    s3_client.delete_object(Bucket=AWS_BUCKET_NAME, Key=file_key) # <--- Correção: s3_client