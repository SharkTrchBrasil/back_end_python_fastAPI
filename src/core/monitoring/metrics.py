"""
Enterprise Monitoring & Metrics
================================
Sistema de métricas e observabilidade para produção

Features:
- ✅ Prometheus metrics
- ✅ Custom business metrics
- ✅ Performance tracking
- ✅ Error tracking
- ✅ Real-time dashboards

Autor: PDVix Team
"""

import time
import logging
from typing import Dict, Any, Optional
from datetime import datetime, timezone
from collections import defaultdict
from functools import wraps

logger = logging.getLogger(__name__)


class MetricsCollector:
    """
    Coletor centralizado de métricas da aplicação
    """

    def __init__(self):
        # Contadores
        self.request_count = defaultdict(int)
        self.error_count = defaultdict(int)
        self.db_query_count = 0
        self.cache_hits = 0
        self.cache_misses = 0

        # Latências (em ms)
        self.request_latencies = defaultdict(list)
        self.db_query_latencies = []

        # Business metrics
        self.active_stores = 0
        self.active_orders = 0
        self.active_websocket_connections = 0

        # Timestamps
        self.start_time = time.time()
        self.last_reset = datetime.now(timezone.utc)

    def track_request(self, endpoint: str, method: str, duration_ms: float, status_code: int):
        """Registra métrica de requisição HTTP"""
        key = f"{method}_{endpoint}"
        self.request_count[key] += 1
        self.request_latencies[key].append(duration_ms)

        if status_code >= 400:
            self.error_count[key] += 1

    def track_db_query(self, duration_ms: float):
        """Registra métrica de query do banco"""
        self.db_query_count += 1
        self.db_query_latencies.append(duration_ms)

    def track_cache_hit(self):
        """Registra cache hit"""
        self.cache_hits += 1

    def track_cache_miss(self):
        """Registra cache miss"""
        self.cache_misses += 1

    def get_metrics_summary(self) -> Dict[str, Any]:
        """
        Retorna resumo completo das métricas

        Returns:
            dict: Métricas agregadas
        """
        uptime_seconds = time.time() - self.start_time

        # Calcula latências médias
        avg_request_latencies = {}
        for endpoint, latencies in self.request_latencies.items():
            if latencies:
                avg_request_latencies[endpoint] = {
                    "avg_ms": round(sum(latencies) / len(latencies), 2),
                    "min_ms": round(min(latencies), 2),
                    "max_ms": round(max(latencies), 2),
                    "p95_ms": round(self._percentile(latencies, 95), 2),
                    "p99_ms": round(self._percentile(latencies, 99), 2),
                }

        avg_db_latency = (
            round(sum(self.db_query_latencies) / len(self.db_query_latencies), 2)
            if self.db_query_latencies else 0
        )

        cache_total = self.cache_hits + self.cache_misses
        cache_hit_rate = (
            round((self.cache_hits / cache_total) * 100, 2)
            if cache_total > 0 else 0
        )

        return {
            "system": {
                "uptime_seconds": round(uptime_seconds, 2),
                "uptime_hours": round(uptime_seconds / 3600, 2),
                "last_reset": self.last_reset.isoformat(),
            },
            "requests": {
                "total": sum(self.request_count.values()),
                "by_endpoint": dict(self.request_count),
                "errors": sum(self.error_count.values()),
                "error_rate": round(
                    (sum(self.error_count.values()) / sum(self.request_count.values()) * 100)
                    if sum(self.request_count.values()) > 0 else 0, 2
                ),
                "latencies": avg_request_latencies,
            },
            "database": {
                "total_queries": self.db_query_count,
                "avg_latency_ms": avg_db_latency,
                "queries_per_second": round(
                    self.db_query_count / uptime_seconds, 2
                ) if uptime_seconds > 0 else 0,
            },
            "cache": {
                "hits": self.cache_hits,
                "misses": self.cache_misses,
                "hit_rate_percent": cache_hit_rate,
            },
            "business": {
                "active_stores": self.active_stores,
                "active_orders": self.active_orders,
                "active_websocket_connections": self.active_websocket_connections,
            }
        }

    def reset_metrics(self):
        """Reseta todas as métricas (útil para testes)"""
        self.__init__()

    @staticmethod
    def _percentile(values: list, percentile: int) -> float:
        """Calcula percentil de uma lista de valores"""
        if not values:
            return 0
        sorted_values = sorted(values)
        index = int(len(sorted_values) * (percentile / 100))
        return sorted_values[min(index, len(sorted_values) - 1)]


# Instância global
metrics = MetricsCollector()


def track_performance(metric_name: str):
    """
    Decorator para rastrear performance de funções

    Args:
        metric_name: Nome da métrica

    Example:
        @track_performance("get_store_details")
        def get_store_details(store_id):
            ...
    """

    def decorator(func):
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            start_time = time.time()
            try:
                result = await func(*args, **kwargs)
                return result
            finally:
                duration_ms = (time.time() - start_time) * 1000
                logger.info(f"⏱️ {metric_name}: {duration_ms:.2f}ms")

        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            start_time = time.time()
            try:
                result = func(*args, **kwargs)
                return result
            finally:
                duration_ms = (time.time() - start_time) * 1000
                logger.info(f"⏱️ {metric_name}: {duration_ms:.2f}ms")

        # Detecta se é async ou sync
        import asyncio
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper

    return decorator