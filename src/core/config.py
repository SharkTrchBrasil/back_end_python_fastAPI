# src/core/config.py
"""
Configurações da Aplicação - MenuHub
====================================

Gerencia variáveis de ambiente de forma centralizada e tipada.

Autor: MenuHub Team
Última atualização: 2025-01-23
"""

from pathlib import Path
from typing import Optional
from dotenv import load_dotenv
from pydantic_settings import BaseSettings

# Carrega .env do diretório raiz
load_dotenv(dotenv_path=Path(__file__).resolve().parent.parent.parent / ".env")


class Config(BaseSettings):
    """Configurações centralizadas da aplicação"""

    # ═══════════════════════════════════════════════════════════
    # 🌍 AMBIENTE
    # ═══════════════════════════════════════════════════════════

    ENVIRONMENT: str = "development"
    DEBUG: bool = False

    # ═══════════════════════════════════════════════════════════
    # 🗄️ BANCO DE DADOS
    # ═══════════════════════════════════════════════════════════

    DATABASE_URL: str

    # ═══════════════════════════════════════════════════════════
    # 🔴 REDIS
    # ═══════════════════════════════════════════════════════════

    REDIS_URL: Optional[str] = None
    RATE_LIMIT_ENABLED: bool = True

    # ═══════════════════════════════════════════════════════════
    # 🔐 JWT (AUTENTICAÇÃO CARDÁPIO)
    # ═══════════════════════════════════════════════════════════

    SECRET_KEY: str
    REFRESH_SECRET_KEY: str
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 30

    # ═══════════════════════════════════════════════════════════
    # ☁️ AWS S3
    # ═══════════════════════════════════════════════════════════

    AWS_ACCESS_KEY_ID: str
    AWS_SECRET_ACCESS_KEY: str
    AWS_REGION: str
    AWS_BUCKET_NAME: str

    # ═══════════════════════════════════════════════════════════
    # 📧 EMAIL (RESEND)
    # ═══════════════════════════════════════════════════════════

    RESEND_API_KEY: str

    # ═══════════════════════════════════════════════════════════
    # 💳 PAGAR.ME
    # ═══════════════════════════════════════════════════════════

    PAGARME_SECRET_KEY: str
    PAGARME_PUBLIC_KEY: str
    PAGARME_ENVIRONMENT: str = "test"
    PAGARME_API_URL: str = "https://api.pagar.me/core/v5"

    # Webhook
    PAGARME_WEBHOOK_USER: str = "menuhub_webhook"
    PAGARME_WEBHOOK_PASSWORD: str

    # ═══════════════════════════════════════════════════════════
    # 💬 CHATBOT
    # ═══════════════════════════════════════════════════════════

    CHATBOT_SERVICE_URL: str
    CHATBOT_WEBHOOK_SECRET: str

    # ═══════════════════════════════════════════════════════════
    # 🔒 CRIPTOGRAFIA
    # ═══════════════════════════════════════════════════════════

    ENCRYPTION_KEY: str

    # ═══════════════════════════════════════════════════════════
    # 🌐 CORS
    # ═══════════════════════════════════════════════════════════

    ALLOWED_ORIGINS: str = "http://localhost:3000"
    PLATFORM_DOMAIN: str = "menuhub.com.br"

    def get_allowed_origins_list(self) -> list[str]:
        """Retorna lista de origens permitidas para CORS"""
        origins = [
            origin.strip()
            for origin in self.ALLOWED_ORIGINS.split(",")
            if origin.strip()
        ]

        # Adiciona origens automáticas em desenvolvimento
        if self.is_development:
            origins.extend([
                "http://localhost:3000",
                "http://localhost:3001",
                "http://127.0.0.1:3000",
            ])

        # Remove duplicatas mantendo ordem
        return list(dict.fromkeys(origins))

    # ═══════════════════════════════════════════════════════════
    # 🖥️ SERVIDOR
    # ═══════════════════════════════════════════════════════════

    HOST: str = "0.0.0.0"
    PORT: int = 8000
    LOG_LEVEL: str = "INFO"

    # ═══════════════════════════════════════════════════════════
    # 🔧 PROPRIEDADES ÚTEIS
    # ═══════════════════════════════════════════════════════════

    @property
    def is_production(self) -> bool:
        return self.ENVIRONMENT.lower() == "production"

    @property
    def is_development(self) -> bool:
        return self.ENVIRONMENT.lower() == "development"

    @property
    def is_test(self) -> bool:
        return self.ENVIRONMENT.lower() == "test"

    @property
    def pagarme_is_production(self) -> bool:
        return self.PAGARME_ENVIRONMENT.lower() == "production"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False


# ✅ Instância global
config = Config()


# ✅ Validação básica no startup
def validate_config():
    """Valida configurações críticas"""
    errors = []

    if len(config.SECRET_KEY) < 32:
        errors.append("SECRET_KEY muito curta (mínimo 32 caracteres)")

    if not config.PAGARME_SECRET_KEY.startswith("sk_"):
        errors.append("PAGARME_SECRET_KEY inválida")

    if config.ENVIRONMENT not in ["development", "test", "production"]:
        errors.append("ENVIRONMENT deve ser: development, test ou production")

    if errors:
        raise ValueError(
            "❌ Erros de configuração:\n" + "\n".join(f"  • {e}" for e in errors)
        )


validate_config()

# Log apenas em desenvolvimento
if config.is_development:
    print("=" * 60)
    print("📋 CONFIGURAÇÃO CARREGADA")
    print("=" * 60)
    print(f"🌍 Ambiente: {config.ENVIRONMENT}")
    print(f"🗄️ Database: {config.DATABASE_URL.split('@')[1] if '@' in config.DATABASE_URL else 'OK'}")
    print(f"💳 Pagar.me: {config.PAGARME_ENVIRONMENT}")
    print(f"🔴 Redis: {'✅' if config.REDIS_URL else '❌'}")
    print(f"🌐 CORS: {len(config.get_allowed_origins_list())} origens")
    print("=" * 60)