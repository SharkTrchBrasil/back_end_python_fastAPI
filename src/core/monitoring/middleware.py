"""
Monitoring Middleware
=====================
Middleware para coletar métricas automaticamente de todas as requisições

Autor: PDVix Team
"""

import time
import logging
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from src.core.monitoring.metrics import metrics

logger = logging.getLogger(__name__)


class MetricsMiddleware(BaseHTTPMiddleware):
    """
    Middleware que captura métricas de todas as requisições HTTP
    """

    async def dispatch(self, request: Request, call_next):
        # Ignora endpoints de health check para não poluir métricas
        if request.url.path in ["/health", "/metrics"]:
            return await call_next(request)

        start_time = time.time()

        # Executa requisição
        try:
            response: Response = await call_next(request)
            status_code = response.status_code
        except Exception as e:
            logger.error(f"❌ Erro na requisição: {e}", exc_info=True)
            status_code = 500
            raise
        finally:
            # Calcula duração
            duration_ms = (time.time() - start_time) * 1000

            # Registra métrica
            metrics.track_request(
                endpoint=request.url.path,
                method=request.method,
                duration_ms=duration_ms,
                status_code=status_code
            )

            # Log estruturado com correlation-id
            cid = getattr(request.state, "correlation_id", None)
            try:
                logger.info(
                    {
                        "event": "http_request",
                        "method": request.method,
                        "path": request.url.path,
                        "status": status_code,
                        "duration_ms": round(duration_ms, 2),
                        "correlationId": cid,
                    }
                )
            except Exception:
                # fallback para string caso handler não aceite dicts
                logger.info(
                    f"event=http_request method={request.method} path={request.url.path} "
                    f"status={status_code} duration_ms={duration_ms:.2f} correlationId={cid}"
                )

            # Log de requisições lentas
            if duration_ms > 1000:  # > 1 segundo
                logger.warning(
                    f"🐌 Requisição lenta: {request.method} {request.url.path} "
                    f"levou {duration_ms:.2f}ms (status: {status_code})"
                )

        return response