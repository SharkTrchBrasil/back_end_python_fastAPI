"""
Middleware de Segurança
=======================
Rate limiting, validação de headers, CORS
"""

from fastapi import Request, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response
import time
import logging
from typing import Callable

from src.core.config import config

logger = logging.getLogger(__name__)


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Middleware para rate limiting"""
    
    def __init__(self, app, calls: int = 60, period: int = 60):
        super().__init__(app)
        self.calls = calls
        self.period = period
        self.clients = {}
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Identifica cliente pelo IP
        client_ip = request.client.host
        
        # Endpoints críticos com limites mais restritivos
        critical_endpoints = {
            "/api/auth/login": (5, 300),        # 5 tentativas em 5 minutos
            "/api/auth/register": (3, 3600),    # 3 registros por hora
            "/api/payments": (10, 60),          # 10 pagamentos por minuto
            "/api/auth/pin-login": (3, 180),    # 3 tentativas de PIN em 3 minutos
        }
        
        # Verifica se é endpoint crítico
        path = request.url.path
        for endpoint, (limit, window) in critical_endpoints.items():
            if path.startswith(endpoint):
                self.calls = limit
                self.period = window
                break
        
        # Limpa clientes antigos
        now = time.time()
        self._clean_old_clients(now)
        
        # Verifica rate limit
        if client_ip in self.clients:
            client_data = self.clients[client_ip]
            if now - client_data["start"] < self.period:
                if client_data["count"] >= self.calls:
                    logger.warning(f"⚠️ Rate limit excedido para {client_ip} em {path}")
                    raise HTTPException(
                        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                        detail="Muitas requisições. Tente novamente mais tarde."
                    )
                client_data["count"] += 1
            else:
                # Reset do contador
                self.clients[client_ip] = {"start": now, "count": 1}
        else:
            self.clients[client_ip] = {"start": now, "count": 1}
        
        # Processa requisição
        response = await call_next(request)
        
        # Adiciona headers de rate limit
        response.headers["X-RateLimit-Limit"] = str(self.calls)
        response.headers["X-RateLimit-Remaining"] = str(
            self.calls - self.clients.get(client_ip, {}).get("count", 0)
        )
        response.headers["X-RateLimit-Reset"] = str(
            int(self.clients.get(client_ip, {}).get("start", now) + self.period)
        )
        
        return response
    
    def _clean_old_clients(self, now: float):
        """Remove clientes com janela expirada"""
        expired = []
        for ip, data in self.clients.items():
            if now - data["start"] > self.period * 2:
                expired.append(ip)
        
        for ip in expired:
            del self.clients[ip]


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Middleware para adicionar headers de segurança"""
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        response = await call_next(request)
        
        # Headers de segurança
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        
        # CSP (Content Security Policy)
        csp = [
            "default-src 'self'",
            "script-src 'self' 'unsafe-inline' https://sdk.mercadopago.com",
            "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com",
            "font-src 'self' https://fonts.gstatic.com",
            "img-src 'self' data: https:",
            "connect-src 'self' https://api.mercadopago.com wss://ws.yourdomain.com"
        ]
        response.headers["Content-Security-Policy"] = "; ".join(csp)
        
        # HSTS (apenas em produção com HTTPS)
        if not config.DEBUG and request.url.scheme == "https":
            response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        
        return response


class TenantValidationMiddleware(BaseHTTPMiddleware):
    """Middleware para validar tenant_id em todas as requisições"""
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Endpoints que não precisam de store_id
        exempt_paths = [
            "/docs",
            "/openapi.json",
            "/api/auth/login",
            "/api/auth/register",
            "/api/auth/refresh",
            "/api/webhook",
            "/health",
        ]
        
        path = request.url.path
        
        # Pula validação para endpoints isentos
        if any(path.startswith(exempt) for exempt in exempt_paths):
            return await call_next(request)
        
        # Extrai store_id do path
        # Padrão: /api/stores/{store_id}/...
        path_parts = path.split("/")
        
        if "stores" in path_parts:
            try:
                store_index = path_parts.index("stores")
                if store_index + 1 < len(path_parts):
                    store_id = path_parts[store_index + 1]
                    
                    # Valida se é número
                    try:
                        int(store_id)
                        # Adiciona ao request state para uso posterior
                        request.state.store_id = store_id
                    except ValueError:
                        logger.warning(f"⚠️ Store ID inválido: {store_id}")
                        raise HTTPException(
                            status_code=status.HTTP_400_BAD_REQUEST,
                            detail="Store ID inválido"
                        )
            except Exception as e:
                logger.error(f"❌ Erro ao extrair store_id: {e}")
        
        return await call_next(request)


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Middleware para log de requisições"""
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Log da requisição
        start_time = time.time()
        
        # Gera request ID único
        import uuid
        request_id = str(uuid.uuid4())[:8]
        request.state.request_id = request_id
        
        logger.info(f"📥 [{request_id}] {request.method} {request.url.path}")
        
        # Processa requisição
        response = await call_next(request)
        
        # Calcula tempo de resposta
        process_time = time.time() - start_time
        
        # Log da resposta
        logger.info(
            f"📤 [{request_id}] {response.status_code} - {process_time:.3f}s"
        )
        
        # Adiciona headers de debug
        response.headers["X-Request-ID"] = request_id
        response.headers["X-Process-Time"] = str(process_time)
        
        return response


def setup_middleware(app):
    """Configura todos os middlewares de segurança"""
    
    # CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=config.CORS_ORIGINS.split(",") if config.CORS_ORIGINS else ["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    # Rate Limiting
    app.add_middleware(RateLimitMiddleware)
    
    # Security Headers
    app.add_middleware(SecurityHeadersMiddleware)
    
    # Tenant Validation
    app.add_middleware(TenantValidationMiddleware)
    
    # Request Logging (apenas em debug)
    if config.DEBUG:
        app.add_middleware(RequestLoggingMiddleware)
    
    logger.info("✅ Middlewares de segurança configurados")
