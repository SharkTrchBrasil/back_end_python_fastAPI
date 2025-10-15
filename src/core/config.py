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

    # Efí Gateway
    MASTER_CLIENT_ID: str
    MASTER_CLIENT_SECRET: str
    MASTER_SANDBOX: bool = False

    # ✅ WEBHOOK TOKEN (Seu próprio secret)
    WEBHOOK_TOKEN: str

    # Chatbot
    CHATBOT_SERVICE_URL: str
    CHATBOT_WEBHOOK_SECRET: str
    PLATFORM_DOMAIN: str

    # ✅ Criptografia
    ENCRYPTION_KEY: str


config = Config()