from pathlib import Path
from dotenv import load_dotenv
from pydantic_settings import BaseSettings, SettingsConfigDict

# Carrega .env da raiz do projeto
load_dotenv(dotenv_path=Path(__file__).resolve().parent.parent.parent / ".env")

class Config(BaseSettings):
    DATABASE_URL: str
    SECRET_KEY: str
    REFRESH_SECRET_KEY: str
    AWS_ACCESS_KEY_ID: str
    AWS_SECRET_ACCESS_KEY: str
    AWS_REGION: str
    AWS_BUCKET_NAME: str
    RESEND_API_KEY: str
    MASTER_CLIENT_ID: str
    MASTER_CLIENT_SECRET: str
    MASTER_SANDBOX: bool = False


    # Chatbot e Plataforma
    CHATBOT_SERVICE_URL: str
    CHATBOT_WEBHOOK_SECRET: str
    PLATFORM_DOMAIN: str


config = Config()
