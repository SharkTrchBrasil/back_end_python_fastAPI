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
Última atualização: 2025-01-19
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

    # ═══════════════════════════════════════════════════════════
    # CORS - ORIGENS PERMITIDAS
    # ═══════════════════════════════════════════════════════════

    ALLOWED_ORIGINS: str = "http://localhost:3000"
    """
    Lista de origens permitidas separadas por vírgula

    Exemplo no .env:
    ALLOWED_ORIGINS=http://localhost:3000,https://menuhub.com.br,https://app.menuhub.com.br

    ⚠️ Em produção, SEMPRE defina explicitamente no .env
    """

    # ═══════════════════════════════════════════════════════════
    # MÉTODOS DE CORS
    # ═══════════════════════════════════════════════════════════

    def get_allowed_origins_list(self) -> list[str]:
        """
        ✅ Retorna lista de origens permitidas para CORS

        Lógica:
        1. Parse das origens do .env
        2. Adiciona origens automáticas baseado no ambiente
        3. Remove duplicatas

        Returns:
            Lista de URLs permitidas
        """
        # Parse das origens do .env
        env_origins = []
        if self.ALLOWED_ORIGINS:
            env_origins = [
                origin.strip()
                for origin in self.ALLOWED_ORIGINS.replace("\n", ",").split(",")
                if origin.strip()
            ]

        # Adiciona origens automáticas baseado no ambiente
        auto_origins = []

        if self.is_development:
            # Desenvolvimento: localhost em várias portas
            auto_origins = [
                "http://localhost:3000",
                "http://localhost:3001",
                "http://localhost:8000",
                "http://127.0.0.1:3000",
                "http://127.0.0.1:3001",
            ]

        elif self.is_production:
            # Produção: domínios registrados
            auto_origins = [
                "https://menuhub.com.br",
                "https://www.menuhub.com.br",
                "https://app.menuhub.com.br",
                "https://admin.menuhub.com.br",
                "https://api-pdvix-production.up.railway.app",
                "https://pdvix-production.up.railway.app",
            ]

        # Combina e remove duplicatas, mantendo a ordem
        seen = set()
        all_origins = []
        for origin in env_origins + auto_origins:
            if origin not in seen:
                seen.add(origin)
                all_origins.append(origin)

        return all_origins

    def get_allowed_methods(self) -> list[str]:
        """
        ✅ Retorna métodos HTTP permitidos para CORS

        Returns:
            Lista de métodos HTTP
        """
        if self.is_development:
            # Em dev, permite tudo para facilitar testes
            return ["*"]
        else:
            # Em produção, restringe a métodos necessários
            return ["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"]

    def get_allowed_headers(self) -> list[str]:
        """
        ✅ Retorna headers permitidos para CORS

        Returns:
            Lista de headers
        """
        return [
            "Accept",
            "Accept-Language",
            "Content-Type",
            "Authorization",
            "X-Requested-With",
            "Totem-Token",
            "X-CSRF-Token",
            "X-Request-ID",
        ]

    def get_expose_headers(self) -> list[str]:
        """
        ✅ Retorna headers expostos para CORS

        Headers que o cliente pode acessar na resposta

        Returns:
            Lista de headers expostos
        """
        return [
            "Content-Length",
            "X-JSON",
            "X-Request-ID",
            "X-Total-Count",
            "X-Page",
            "X-Per-Page",
        ]


    # ═══════════════════════════════════════════════════════════
    # REDIS
    # ═══════════════════════════════════════════════════════════

    REDIS_URL: Optional[str] = None

    # Configurações de Rate Limiting
    RATE_LIMIT_ENABLED: bool = True
    RATE_LIMIT_STORAGE_URL: Optional[str] = None

    # ═══════════════════════════════════════════════════════════
    # DATABASE
    # ═══════════════════════════════════════════════════════════

    DATABASE_URL: str
    DATABASE_READ_REPLICA_URL: Optional[str] = None

    # Pool de Conexões
    DB_POOL_SIZE: int = 50
    DB_MAX_OVERFLOW: int = 50
    DB_POOL_TIMEOUT: int = 10
    DB_POOL_RECYCLE: int = 1800

    # Retry Logic
    DB_MAX_RETRIES: int = 3
    DB_RETRY_DELAY: float = 0.5

    # Circuit Breaker
    DB_CIRCUIT_BREAKER_THRESHOLD: int = 5
    DB_CIRCUIT_BREAKER_TIMEOUT: int = 30

    # Query Timeouts
    DB_STATEMENT_TIMEOUT: int = 30000  # 30 segundos
    DB_CONNECT_TIMEOUT: int = 10  # 10 segundos

    # ═══════════════════════════════════════════════════════════
    # AUTENTICAÇÃO JWT
    # ═══════════════════════════════════════════════════════════

    SECRET_KEY: str
    REFRESH_SECRET_KEY: str
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

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
    PAGARME_ENVIRONMENT: str = "test"
    PAGARME_API_URL: str = "https://api.pagar.me/core/v5"

    # Webhook - Autenticação Básica
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

    LOG_LEVEL: str = "INFO"

    # ═══════════════════════════════════════════════════════════
    # PROPRIEDADES E MÉTODOS ÚTEIS
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

    def get_allowed_origins_list(self) -> list[str]:
        """
        ✅ Retorna lista de origens permitidas para CORS

        Transforma a string separada por vírgulas em uma lista

        Returns:
            Lista de URLs permitidas
        """
        if not self.ALLOWED_ORIGINS:
            return []

        # Remove espaços e quebras de linha, depois divide por vírgula
        origins = [
            origin.strip()
            for origin in self.ALLOWED_ORIGINS.replace("\n", ",").split(",")
            if origin.strip()
        ]

        return origins

    def get_allowed_methods(self) -> list[str]:
        """
        ✅ Retorna métodos HTTP permitidos para CORS

        Returns:
            Lista de métodos HTTP
        """
        if self.is_development:
            # Em dev, permite tudo para facilitar testes
            return ["*"]
        else:
            # Em produção, restringe a métodos necessários
            return ["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"]

    def get_allowed_headers(self) -> list[str]:
        """
        ✅ Retorna headers permitidos para CORS

        Returns:
            Lista de headers
        """
        return [
            "Accept",
            "Accept-Language",
            "Content-Type",
            "Authorization",
            "X-Requested-With",
            "Totem-Token",
            "X-CSRF-Token",
        ]

    def get_expose_headers(self) -> list[str]:
        """
        ✅ Retorna headers expostos para CORS

        Returns:
            Lista de headers expostos
        """
        return [
            "Content-Length",
            "X-JSON",
            "X-Request-ID",
        ]

    class Config:
        """Configuração do Pydantic"""
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False
        extra = "forbid"  # ✅ Proíbe campos extras não declarados


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

    # Valida ALLOWED_ORIGINS
    origins = config.get_allowed_origins_list()
    if not origins:
        errors.append("ALLOWED_ORIGINS não pode estar vazia")

    # Valida formato de cada origem
    for origin in origins:
        if not (origin.startswith("http://") or origin.startswith("https://")):
            errors.append(f"Origem inválida '{origin}' - deve começar com http:// ou https://")

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
    print(f"Pagar.me: {config.PAGARME_ENVIRONMENT}")
    print(f"CORS Origins: {len(config.get_allowed_origins_list())} origens")
    print(f"Redis: {'✅ Configurado' if config.REDIS_URL else '❌ Não configurado'}")
    print(f"Rate Limiting: {'✅ Ativo' if config.RATE_LIMIT_ENABLED else '❌ Desativado'}")
    print(f"Log Level: {config.LOG_LEVEL}")
    print("=" * 60)