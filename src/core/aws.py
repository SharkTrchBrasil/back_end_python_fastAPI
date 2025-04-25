import uuid

import boto3
from fastapi import UploadFile

from src.core.config import config

s3_client = boto3.client(
    's3',
    aws_access_key_id=config.AWS_ACCESS_KEY,
    aws_secret_access_key=config.AWS_SECRET_KEY,
    region_name=config.AWS_REGION
)

def upload_file(file) -> str:
    file_key = f"{uuid.uuid4()}_{file.filename}"
    s3_client.upload_fileobj(file.file, config.AWS_BUCKET_NAME, file_key)

    return file_key


def get_presigned_url(file_key: str) -> str:
    pre_signed_url = s3_client.generate_presigned_url(
        'get_object',
        Params={'Bucket': config.AWS_BUCKET_NAME, 'Key': file_key},
        ExpiresIn=86400 # 24 hours (60 * 60 * 24)
    )

    return pre_signed_url

def delete_file(file_key: str) -> None:
    s3_client.delete_object(Bucket=config.AWS_BUCKET_NAME, Key=file_key)