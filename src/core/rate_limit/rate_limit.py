# src/core/rate_limit/rate_limit.py

"""
Sistema de Rate Limiting Profissional para MenuHub
===================================================
Protege contra DDoS, brute force e abuso de API

Última atualização: 2025-01-19
"""

import logging
from typing import Callable
from slowapi import Limiter
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from starlette.requests import Request
from starlette.responses import JSONResponse
from src.core.config import config
import redis

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════
# CONFIGURAÇÃO DO STORAGE (Redis ou Memória)
# ═══════════════════════════════════════════════════════════

def get_storage_uri() -> str:
    """
    Retorna URI do storage para rate limiting

    Prioridade:
    1. Redis (produção) - persistente e distribuído
    2. Memory (desenvolvimento) - temporário
    """
    if config.REDIS_URL:
        logger.info(f"✅ Rate Limiting usando Redis: {config.REDIS_URL[:30]}...")
        return config.REDIS_URL

    logger.warning("⚠️ Rate Limiting usando memória (não recomendado em produção)")
    return "memory://"


# ═══════════════════════════════════════════════════════════
# FUNÇÃO PARA IDENTIFICAR USUÁRIO
# ═══════════════════════════════════════════════════════════

def get_identifier(request: Request) -> str:
    """
    Identifica o cliente para rate limiting

    Prioridade:
    1. User ID (se autenticado) - mais preciso
    2. IP Address (se anônimo) - fallback
    """
    # 1. Tenta pegar user_id do token JWT (se autenticado)
    try:
        if hasattr(request.state, "user") and request.state.user:
            user_id = getattr(request.state.user, "id", None)
            if user_id:
                return f"user:{user_id}"
    except:
        pass

    # 2. Fallback: usa IP address
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        ip = forwarded.split(",")[0].strip()
    else:
        ip = request.client.host if request.client else "unknown"

    return f"ip:{ip}"


# ═══════════════════════════════════════════════════════════
# INICIALIZAÇÃO DO LIMITER (CONFIGURAÇÃO CORRIGIDA)
# ═══════════════════════════════════════════════════════════

limiter = Limiter(
    key_func=get_identifier,
    storage_uri=get_storage_uri(),
    default_limits=["1000/hour"],
    headers_enabled=True,
    swallow_errors=True,
    # ✅ CRÍTICO: Esta configuração previne o erro do SlowAPI
    strategy="fixed-window",
    # ✅ Desabilita injeção automática de headers (FastAPI faz isso depois)
    auto_check=False,
)

logger.info(f"✅ Rate Limiter inicializado com storage: {get_storage_uri()[:30]}")


# ═══════════════════════════════════════════════════════════
# HANDLER DE ERRO CUSTOMIZADO (MELHORADO)
# ═══════════════════════════════════════════════════════════

async def rate_limit_exceeded_handler(request: Request, exc: RateLimitExceeded) -> JSONResponse:
    """
    ✅ Handler assíncrono para rate limit excedido

    Retorna JSONResponse diretamente (compatível com FastAPI)
    """
    path = request.url.path
    method = request.method
    identifier = get_identifier(request)

    # Log de segurança
    logger.warning(
        f"🚨 RATE LIMIT EXCEDIDO\n"
        f"   ├─ Path: {method} {path}\n"
        f"   ├─ Identificador: {identifier}\n"
        f"   ├─ Limite: {exc.detail}\n"
        f"   └─ User-Agent: {request.headers.get('user-agent', 'N/A')[:100]}"
    )

    # ✅ Extrai informações do erro
    retry_after = 60  # Padrão: 1 minuto
    try:
        if hasattr(exc, 'retry_after'):
            retry_after = int(exc.retry_after)
        elif "Retry after" in exc.detail:
            retry_after = int(exc.detail.split("Retry after ")[1].split(" ")[0])
    except:
        pass

    # ✅ Resposta JSON profissional
    return JSONResponse(
        status_code=429,
        content={
            "error": "too_many_requests",
            "message": "Muitas requisições. Por favor, aguarde alguns segundos.",
            "detail": exc.detail,
            "retry_after_seconds": retry_after,
        },
        headers={
            "Retry-After": str(retry_after),
            "X-RateLimit-Remaining": "0",
        }
    )


# ═══════════════════════════════════════════════════════════
# RATE LIMITS PRÉ-CONFIGURADOS
# ═══════════════════════════════════════════════════════════

RATE_LIMITS = {
    # Autenticação (mais restritivo)
    "login": "5/minute",
    "register": "3/minute",
    "password_reset": "3/hour",

    # Operações normais
    "read": "100/minute",
    "write": "30/minute",

    # Webhooks
    "webhook": "1000/hour",

    # WebSocket
    "websocket_connect": "10/minute",

    # Admin operations
    "admin_write": "60/minute",

    # Endpoints públicos
    "public": "200/minute",
}


# ═══════════════════════════════════════════════════════════
# WRAPPER PARA COMPATIBILIDADE COM FASTAPI
# ═══════════════════════════════════════════════════════════

def rate_limit(limit_string: str):
    """
    ✅ Wrapper profissional que garante compatibilidade total

    Uso:
    ```python
    @router.post("/login")
    @rate_limit("5/minute")
    async def login(...):
        return {"token": "..."}  # Retorna dict normal
    ```
    """
    def decorator(func: Callable) -> Callable:
        # ✅ Aplica limiter mas não tenta modificar resposta dict
        limited_func = limiter.limit(limit_string)(func)

        # ✅ Marca função para FastAPI processar corretamente
        limited_func.__rate_limited__ = True
        limited_func.__rate_limit__ = limit_string

        return limited_func

    return decorator


# ═══════════════════════════════════════════════════════════
# FUNÇÕES AUXILIARES
# ═══════════════════════════════════════════════════════════

def check_redis_connection() -> bool:
    """Verifica se Redis está acessível"""
    if not config.REDIS_URL:
        return False

    try:
        r = redis.from_url(config.REDIS_URL, socket_connect_timeout=2)
        r.ping()
        logger.info("✅ Conexão com Redis OK")
        return True
    except Exception as e:
        logger.error(f"❌ Erro ao conectar no Redis: {e}")
        return False


def get_rate_limit_info(request: Request) -> dict:
    """Retorna informações sobre rate limiting"""
    return {
        "rate_limit_enabled": config.RATE_LIMIT_ENABLED,
        "storage": "redis" if config.REDIS_URL else "memory",
        "identifier": get_identifier(request),
    }