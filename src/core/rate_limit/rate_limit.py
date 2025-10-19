# src/core/rate_limit/rate_limit.py

"""
Sistema de Rate Limiting Profissional
======================================
Compatível com FastAPI moderno - SEM decorators problemáticos
"""

import logging
from typing import Callable, Optional
from slowapi import Limiter
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from starlette.requests import Request
from starlette.responses import JSONResponse
from fastapi import Depends, HTTPException
from src.core.config import config
import redis

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════
# CONFIGURAÇÃO
# ═══════════════════════════════════════════════════════════

def get_storage_uri() -> str:
    """Retorna URI do storage"""
    if config.REDIS_URL:
        logger.info(f"✅ Rate Limiting usando Redis")
        return config.REDIS_URL

    logger.warning("⚠️ Rate Limiting usando memória")
    return "memory://"


def get_identifier(request: Request) -> str:
    """Identifica o cliente"""
    try:
        if hasattr(request.state, "user") and request.state.user:
            user_id = getattr(request.state.user, "id", None)
            if user_id:
                return f"user:{user_id}"
    except:
        pass

    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        ip = forwarded.split(",")[0].strip()
    else:
        ip = request.client.host if request.client else "unknown"

    return f"ip:{ip}"


# ═══════════════════════════════════════════════════════════
# LIMITER (SEM auto_check)
# ═══════════════════════════════════════════════════════════

limiter = Limiter(
    key_func=get_identifier,
    storage_uri=get_storage_uri(),
    default_limits=["1000/hour"],
    headers_enabled=True,
    swallow_errors=True,
)

logger.info(f"✅ Rate Limiter inicializado")

# ═══════════════════════════════════════════════════════════
# RATE LIMITS
# ═══════════════════════════════════════════════════════════

RATE_LIMITS = {
    "login": "5/minute",
    "register": "3/minute",
    "password_reset": "3/hour",
    "read": "100/minute",
    "write": "30/minute",
    "webhook": "1000/hour",
    "websocket_connect": "10/minute",
    "admin_write": "60/minute",
    "public": "200/minute",
}


# ═══════════════════════════════════════════════════════════
# DEPENDENCY INJECTION (SOLUÇÃO PROFISSIONAL)
# ═══════════════════════════════════════════════════════════

class RateLimitDependency:
    """
    ✅ Dependency para rate limiting compatível com FastAPI

    Uso:
    ```python
    @router.post("/login")
    async def login(
        request: Request,
        _rate_limit: None = Depends(RateLimitDependency("5/minute"))
    ):
        return {"token": "..."}
    ```
    """

    def __init__(self, limit: str):
        self.limit = limit

    async def __call__(self, request: Request) -> None:
        """Verifica rate limit"""
        try:
            # Obtém identificador
            identifier = get_identifier(request)

            # Verifica limite usando o limiter interno
            if not limiter._storage:
                return  # Storage não disponível, permite requisição

            # Monta chave do Redis
            key = f"rl:{identifier}:{request.url.path}"

            # Parseia limite (ex: "5/minute" -> 5, 60)
            limit_parts = self.limit.split("/")
            max_requests = int(limit_parts[0])

            # Mapeia período para segundos
            period_map = {
                "second": 1,
                "minute": 60,
                "hour": 3600,
                "day": 86400
            }

            period_str = limit_parts[1] if len(limit_parts) > 1 else "minute"
            period_seconds = period_map.get(period_str, 60)

            # Verifica no storage
            current = limiter._storage.get(key)

            if current is None:
                # Primeira requisição
                limiter._storage.set(key, 1, expire=period_seconds)
                return

            current_count = int(current)

            if current_count >= max_requests:
                # Limite excedido
                logger.warning(
                    f"🚨 Rate limit excedido: {identifier} "
                    f"em {request.url.path} ({current_count}/{max_requests})"
                )
                raise HTTPException(
                    status_code=429,
                    detail={
                        "error": "too_many_requests",
                        "message": "Muitas requisições. Aguarde alguns segundos.",
                        "retry_after_seconds": period_seconds
                    }
                )

            # Incrementa contador
            limiter._storage.incr(key)

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Erro no rate limiting: {e}")
            # Em caso de erro, permite requisição (fail-safe)
            return


# ═══════════════════════════════════════════════════════════
# EXCEPTION HANDLER
# ═══════════════════════════════════════════════════════════

async def rate_limit_exceeded_handler(request: Request, exc: RateLimitExceeded) -> JSONResponse:
    """Handler para rate limit excedido"""
    path = request.url.path
    method = request.method
    identifier = get_identifier(request)

    logger.warning(
        f"🚨 RATE LIMIT EXCEDIDO\n"
        f"   ├─ Path: {method} {path}\n"
        f"   ├─ Identificador: {identifier}\n"
        f"   └─ User-Agent: {request.headers.get('user-agent', 'N/A')[:100]}"
    )

    return JSONResponse(
        status_code=429,
        content={
            "error": "too_many_requests",
            "message": "Muitas requisições. Por favor, aguarde alguns segundos.",
            "retry_after_seconds": 60,
        },
        headers={
            "Retry-After": "60",
            "X-RateLimit-Remaining": "0",
        }
    )


# ═══════════════════════════════════════════════════════════
# FUNÇÕES AUXILIARES
# ═══════════════════════════════════════════════════════════

def check_redis_connection() -> bool:
    """Verifica conexão Redis"""
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