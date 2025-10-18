"""
Sistema de Rate Limiting para MenuHub
Protege contra DDoS, brute force e abuso de API
"""
import logging
from slowapi import Limiter
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from starlette.requests import Request
from starlette.responses import JSONResponse
from typing import Optional
from src.core.config import config
import redis

logger = logging.getLogger(__name__)


# ==========================================
# CONFIGURAÇÃO DO STORAGE (Redis ou Memória)
# ==========================================

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


# ==========================================
# FUNÇÃO PARA IDENTIFICAR USUÁRIO
# ==========================================

def get_identifier(request: Request) -> str:
    """
    Identifica o cliente para rate limiting

    Prioridade:
    1. User ID (se autenticado) - mais preciso
    2. IP Address (se anônimo) - fallback

    Isso evita que um usuário legítimo seja bloqueado
    por compartilhar IP (ex: mesma empresa)
    """

    # 1. Tenta pegar user_id do token JWT (se autenticado)
    try:
        # Se o usuário está autenticado, usa seu ID
        if hasattr(request.state, "user") and request.state.user:
            user_id = getattr(request.state.user, "id", None)
            if user_id:
                return f"user:{user_id}"
    except:
        pass

    # 2. Fallback: usa IP address
    # Considera X-Forwarded-For (Railway/proxy)
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        ip = forwarded.split(",")[0].strip()
    else:
        ip = request.client.host if request.client else "unknown"

    return f"ip:{ip}"


# ==========================================
# INICIALIZAÇÃO DO LIMITER
# ==========================================

limiter = Limiter(
    key_func=get_identifier,  # ✅ Usa nossa função customizada
    storage_uri=get_storage_uri(),  # ✅ Redis ou memória
    default_limits=["1000/hour"],  # ✅ Limite global padrão
    headers_enabled=True,  # ✅ Retorna headers informativos
    swallow_errors=True,  # ✅ Não quebra se Redis cair (fallback para sem limite)
)

logger.info(f"✅ Rate Limiter inicializado com storage: {get_storage_uri()[:30]}")


# ==========================================
# HANDLER DE ERRO CUSTOMIZADO
# ==========================================

def rate_limit_exceeded_handler(request: Request, exc: RateLimitExceeded) -> JSONResponse:
    """
    Retorna resposta amigável quando rate limit é excedido
    """

    # Extrai informações do erro
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

    # Resposta para o cliente
    return JSONResponse(
        status_code=429,
        content={
            "error": "too_many_requests",
            "message": "Muitas requisições. Por favor, aguarde alguns segundos.",
            "detail": exc.detail,
            "retry_after": getattr(exc, "retry_after", 60),  # Segundos até poder tentar novamente
        },
        headers={
            "Retry-After": str(getattr(exc, "retry_after", 60)),
            "X-RateLimit-Limit": str(getattr(exc, "limit", "N/A")),
            "X-RateLimit-Remaining": "0",
            "X-RateLimit-Reset": str(getattr(exc, "reset", "N/A")),
        }
    )


# ==========================================
# DECORATORS ESPECÍFICOS PARA CADA CENÁRIO
# ==========================================

# ✅ Rate limits pré-configurados
RATE_LIMITS = {
    # Autenticação (mais restritivo)
    "login": "5/minute",  # Máx 5 tentativas de login por minuto
    "register": "3/minute",  # Máx 3 cadastros por minuto (previne spam)
    "password_reset": "3/hour",  # Máx 3 resets de senha por hora

    # Operações normais
    "read": "100/minute",  # Leitura (GET) - mais permissivo
    "write": "30/minute",  # Escrita (POST/PUT/DELETE) - mais restritivo

    # Webhooks
    "webhook": "1000/hour",  # Webhooks de pagamento

    # WebSocket
    "websocket_connect": "10/minute",  # Máx 10 conexões por minuto (previne spam)

    # Admin operations
    "admin_write": "60/minute",  # Admins podem fazer mais operações

    # Endpoints públicos (cardápio)
    "public": "200/minute",  # Mais permissivo para clientes finais
}


# ==========================================
# FUNÇÕES AUXILIARES
# ==========================================

def check_redis_connection() -> bool:
    """
    Verifica se Redis está acessível
    """
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
    """
    Retorna informações sobre rate limiting para o cliente
    """
    return {
        "rate_limit_enabled": config.RATE_LIMIT_ENABLED,
        "storage": "redis" if config.REDIS_URL else "memory",
        "identifier": get_identifier(request),
    }