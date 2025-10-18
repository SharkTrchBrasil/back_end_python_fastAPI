# src/core/config.py
"""
Configurações da Aplicação
==========================

Gerencia todas as variáveis de ambiente de forma centralizada e tipada.

Características:
- ✅ Validação automática via Pydantic
- ✅ Type hints para IDE autocomplete
- ✅ Valores padrão seguros
- ✅ Ambiente configurável (dev/test/prod)

Autor: PDVix Team
Última atualização: 2025-01-18
"""

from pathlib import Path
from typing import Optional
from dotenv import load_dotenv
from pydantic_settings import BaseSettings

# ✅ Carrega .env do diretório raiz do projeto
load_dotenv(dotenv_path=Path(__file__).resolve().parent.parent.parent / ".env")


class Config(BaseSettings):
    """
    ✅ CONFIGURAÇÕES CENTRALIZADAS DA APLICAÇÃO

    Todas as variáveis de ambiente são validadas automaticamente.
    Se uma variável obrigatória estiver faltando, a aplicação não inicia.
    """

    # ═══════════════════════════════════════════════════════════
    # AMBIENTE
    # ═══════════════════════════════════════════════════════════

    ENVIRONMENT: str = "development"  # development, test, production
    DEBUG: bool = False

    # ✅ Redis para Rate Limiting (BUG #2)
    REDIS_URL: Optional[str] = None

    # ✅ Configurações de Rate Limiting (BUG #2)
    RATE_LIMIT_ENABLED: bool = True
    RATE_LIMIT_STORAGE_URL: Optional[str] = None  # Usa Redis se disponível, senão memória

    # ═══════════════════════════════════════════════════════════
    # DATABASE
    # ═══════════════════════════════════════════════════════════

    DATABASE_URL: str

    # ═══════════════════════════════════════════════════════════
    # AUTENTICAÇÃO JWT
    # ═══════════════════════════════════════════════════════════

    SECRET_KEY: str
    REFRESH_SECRET_KEY: str
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 30

    # ═══════════════════════════════════════════════════════════
    # AWS S3
    # ═══════════════════════════════════════════════════════════

    AWS_ACCESS_KEY_ID: str
    AWS_SECRET_ACCESS_KEY: str
    AWS_REGION: str
    AWS_BUCKET_NAME: str

    # ═══════════════════════════════════════════════════════════
    # EMAIL (RESEND)
    # ═══════════════════════════════════════════════════════════

    RESEND_API_KEY: str

    # ═══════════════════════════════════════════════════════════
    # PAGAR.ME (PAGAMENTO)
    # ═══════════════════════════════════════════════════════════

    PAGARME_SECRET_KEY: str
    PAGARME_PUBLIC_KEY: str

    PAGARME_ENVIRONMENT: str = "test"  # test ou production
    PAGARME_API_URL: str = "https://api.pagar.me/core/v5"

    # ✅ Webhook - Autenticação Básica
    PAGARME_WEBHOOK_USER: str = "pagarme_webhook"
    PAGARME_WEBHOOK_PASSWORD: str

    # ═══════════════════════════════════════════════════════════
    # CHATBOT
    # ═══════════════════════════════════════════════════════════

    CHATBOT_SERVICE_URL: str
    CHATBOT_WEBHOOK_SECRET: str
    PLATFORM_DOMAIN: str

    # ═══════════════════════════════════════════════════════════
    # CRIPTOGRAFIA
    # ═══════════════════════════════════════════════════════════

    ENCRYPTION_KEY: str

    # ═══════════════════════════════════════════════════════════
    # SERVIDOR
    # ═══════════════════════════════════════════════════════════

    HOST: str = "0.0.0.0"
    PORT: int = 8000

    # ═══════════════════════════════════════════════════════════
    # LOGGING
    # ═══════════════════════════════════════════════════════════

    LOG_LEVEL: str = "INFO"  # DEBUG, INFO, WARNING, ERROR, CRITICAL

    # ═══════════════════════════════════════════════════════════
    # MÉTODOS ÚTEIS
    # ═══════════════════════════════════════════════════════════

    @property
    def is_production(self) -> bool:
        """Verifica se está em produção"""
        return self.ENVIRONMENT.lower() == "production"

    @property
    def is_development(self) -> bool:
        """Verifica se está em desenvolvimento"""
        return self.ENVIRONMENT.lower() == "development"

    @property
    def is_test(self) -> bool:
        """Verifica se está em teste"""
        return self.ENVIRONMENT.lower() == "test"

    @property
    def pagarme_is_production(self) -> bool:
        """Verifica se Pagar.me está em modo produção"""
        return self.PAGARME_ENVIRONMENT.lower() == "production"

    def get_database_url(self, hide_password: bool = False) -> str:
        """
        Retorna URL do banco (opcionalmente mascarando senha)

        Args:
            hide_password: Se True, mascara a senha para logs

        Returns:
            URL do banco de dados
        """
        if not hide_password:
            return self.DATABASE_URL

        # Mascara senha para logs
        parts = self.DATABASE_URL.split("@")
        if len(parts) == 2:
            credentials, rest = parts
            if ":" in credentials:
                user, _ = credentials.rsplit(":", 1)
                return f"{user}:****@{rest}"

        return self.DATABASE_URL

    class Config:
        """Configuração do Pydantic"""
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False  # Aceita variáveis em minúsculas também


# ✅ INSTÂNCIA GLOBAL (SINGLETON)
config = Config()


# ✅ VALIDAÇÃO NO IMPORT
def validate_config():
    """
    Valida configurações críticas no startup

    Raises:
        ValueError: Se alguma configuração crítica estiver inválida
    """
    errors = []

    # Valida SECRET_KEY
    if len(config.SECRET_KEY) < 32:
        errors.append("SECRET_KEY deve ter no mínimo 32 caracteres")

    # Valida PAGARME_SECRET_KEY
    if not config.PAGARME_SECRET_KEY.startswith("sk_"):
        errors.append("PAGARME_SECRET_KEY deve começar com 'sk_'")

    # Valida PAGARME_ENVIRONMENT
    if config.PAGARME_ENVIRONMENT not in ["test", "production"]:
        errors.append("PAGARME_ENVIRONMENT deve ser 'test' ou 'production'")

    # Valida ENVIRONMENT
    if config.ENVIRONMENT not in ["development", "test", "production"]:
        errors.append("ENVIRONMENT deve ser 'development', 'test' ou 'production'")

    if errors:
        raise ValueError(
            f"Erros de configuração encontrados:\n" + "\n".join(f"- {e}" for e in errors)
        )


# ✅ Executa validação no import
validate_config()

# ✅ LOG DE CONFIGURAÇÃO (apenas se não for produção)
if not config.is_production:
    print("=" * 60)
    print("📋 CONFIGURAÇÃO CARREGADA")
    print("=" * 60)
    print(f"Environment: {config.ENVIRONMENT}")
    print(f"Debug: {config.DEBUG}")
    print(f"Database: {config.get_database_url(hide_password=True)}")
    print(f"Pagar.me Environment: {config.PAGARME_ENVIRONMENT}")
    print(f"Log Level: {config.LOG_LEVEL}")
    print("=" * 60)