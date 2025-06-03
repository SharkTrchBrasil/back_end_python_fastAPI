from pathlib import Path
from dotenv import load_dotenv
from pydantic_settings import BaseSettings, SettingsConfigDict

# Carrega .env da raiz do projeto
load_dotenv(dotenv_path=Path(__file__).resolve().parent.parent.parent / ".env")

class Config(BaseSettings):
    DATABASE_URL: str
    SECRET_KEY: str
    REFRESH_SECRET_KEY: str
    AWS_ACCESS_KEY: str
    AWS_SECRET_KEY: str
    AWS_REGION: str
    AWS_BUCKET_NAME: str
    RESEND_API_KEY: str

config = Config()
