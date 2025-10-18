"""
Configuração segura de CORS para MenuHub
Autor: Sistema de Segurança PDVix
Data: 2025-10-18
"""
from typing import List
from src.core.config import config
import logging

logger = logging.getLogger(__name__)

def get_allowed_origins() -> List[str]:
    """
    Retorna lista de origens permitidas baseado no ambiente

    ✅ Produção: Apenas domínios oficiais do MenuHub
    🛠️ Desenvolvimento: Localhost para testes
    """

    # 🔒 PRODUÇÃO - Domínios oficiais
    if config.ENVIRONMENT == "production":
        origins = [
            # ✅ Domínio principal
            "https://menuhub.com.br",
            "https://www.menuhub.com.br",

            # ✅ Subdomínios oficiais (se tiver)
            "https://app.menuhub.com.br",
            "https://admin.menuhub.com.br",
            "https://painel.menuhub.com.br",

            # ✅ Backend (para testes internos via Swagger)
            "https://api-pdvix-production.up.railway.app",
        ]
        logger.info(f"🔒 CORS PRODUÇÃO: {len(origins)} origens autorizadas")
        return origins

    # 🛠️ DESENVOLVIMENTO - Localhost + Railway
    elif config.ENVIRONMENT == "development":
        origins = [
            # Frontend local (Flutter web/React)
            "http://localhost:3000",
            "http://localhost:8080",
            "http://localhost:5173",  # Vite
            "http://127.0.0.1:3000",
            "http://127.0.0.1:8080",

            # Backend Railway (desenvolvimento)
            "https://api-pdvix-production.up.railway.app",

            # Domínio de produção (para testes)
            "https://menuhub.com.br",
            "https://www.menuhub.com.br",
        ]
        logger.info(f"🛠️ CORS DESENVOLVIMENTO: {len(origins)} origens (inclui localhost)")
        return origins

    # 🧪 STAGING - Ambiente de homologação
    elif config.ENVIRONMENT == "staging":
        origins = [
            "https://staging.menuhub.com.br",
            "https://dev.menuhub.com.br",
            "https://api-pdvix-production.up.railway.app",
        ]
        logger.info(f"🧪 CORS STAGING: {len(origins)} origens")
        return origins

    # ⚠️ Fallback seguro (caso ENVIRONMENT não esteja definido)
    logger.warning("⚠️ ENVIRONMENT não definido! Usando fallback seguro.")
    return [
        "https://menuhub.com.br",
        "https://api-pdvix-production.up.railway.app"
    ]


def get_allowed_methods() -> List[str]:
    """
    Métodos HTTP permitidos (princípio do menor privilégio)

    ✅ Apenas os métodos realmente necessários
    """
    return ["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"]


def get_allowed_headers() -> List[str]:
    """
    Headers HTTP permitidos (apenas o necessário)

    ✅ Lista restrita para segurança máxima
    """
    return [
        "Authorization",      # JWT tokens
        "Content-Type",       # application/json
        "Accept",            # Aceita resposta
        "Origin",            # CORS
        "X-Requested-With",  # Ajax requests
        "X-Store-ID",        # Identificação da loja (multi-tenant)
        "X-Device-ID",       # Identificação do dispositivo
    ]


def get_expose_headers() -> List[str]:
    """
    Headers que o frontend pode ler na resposta
    """
    return [
        "X-Total-Count",     # Paginação
        "X-Page-Number",     # Número da página
        "X-Rate-Limit",      # Rate limiting info
    ]