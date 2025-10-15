from pathlib import Path
from dotenv import load_dotenv
from pydantic_settings import BaseSettings

load_dotenv(dotenv_path=Path(__file__).resolve().parent.parent.parent / ".env")


class Config(BaseSettings):
    # Database
    DATABASE_URL: str

    # Auth
    SECRET_KEY: str
    REFRESH_SECRET_KEY: str
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 30

    # AWS
    AWS_ACCESS_KEY_ID: str
    AWS_SECRET_ACCESS_KEY: str
    AWS_REGION: str
    AWS_BUCKET_NAME: str

    # Email
    RESEND_API_KEY: str

    # ✅ PAGAR.ME (NOVO)
    PAGARME_SECRET_KEY: str
    PAGARME_PUBLIC_KEY: str
    PAGARME_WEBHOOK_SECRET: str
    PAGARME_ENVIRONMENT: str = "test"
    PAGARME_API_URL: str = "https://api.pagar.me/core/v5"


    # ✅ WEBHOOK - Autenticação Básica
    PAGARME_WEBHOOK_USER: str
    PAGARME_WEBHOOK_PASSWORD: str



    # Chatbot
    CHATBOT_SERVICE_URL: str
    CHATBOT_WEBHOOK_SECRET: str
    PLATFORM_DOMAIN: str

    # Criptografia
    ENCRYPTION_KEY: str


config = Config()