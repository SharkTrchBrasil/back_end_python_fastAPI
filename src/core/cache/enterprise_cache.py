"""
Enterprise Cache Layer
======================
Sistema de cache em múltiplas camadas para alta performance

Camadas:
1. L1: Cache em memória (local)
2. L2: Redis (compartilhado)
3. L3: Database

Autor: PDVix Team
"""

import hashlib
import json
import pickle
from typing import Any, Optional, Callable
from functools import wraps
import logging

from src.core.cache.redis_client import redis_client

logger = logging.getLogger(__name__)


class MultiLayerCache:
    """
    Cache em múltiplas camadas com fallback automático
    """

    def __init__(self):
        self.l1_cache = {}  # Cache em memória (limitado a 1000 itens)
        self.l1_max_size = 1000
        self.l1_hits = 0
        self.l2_hits = 0
        self.l3_hits = 0
        self.misses = 0

    def _generate_key(self, prefix: str, *args, **kwargs) -> str:
        """Gera chave única baseada nos parâmetros"""
        key_data = f"{prefix}:{args}:{sorted(kwargs.items())}"
        return hashlib.md5(key_data.encode()).hexdigest()

    def get(self, key: str) -> Optional[Any]:
        """
        Busca valor no cache (L1 -> L2 -> None)

        Args:
            key: Chave do cache

        Returns:
            Valor cacheado ou None
        """
        # L1: Memória local
        if key in self.l1_cache:
            self.l1_hits += 1
            logger.debug(f"🎯 L1 Cache HIT: {key}")
            return self.l1_cache[key]

        # L2: Redis
        if redis_client.is_available:
            value = redis_client.get(key)
            if value is not None:
                self.l2_hits += 1
                logger.debug(f"🎯 L2 Cache HIT: {key}")
                # Promove para L1
                self._set_l1(key, value)
                return value

        self.misses += 1
        logger.debug(f"❌ Cache MISS: {key}")
        return None

    def set(self, key: str, value: Any, ttl: int = 300):
        """
        Armazena valor em todas as camadas de cache

        Args:
            key: Chave do cache
            value: Valor a ser cacheado
            ttl: Time to live em segundos
        """
        # L1: Memória local
        self._set_l1(key, value)

        # L2: Redis
        if redis_client.is_available:
            redis_client.set(key, value, ttl)

    def _set_l1(self, key: str, value: Any):
        """Armazena em L1 com limite de tamanho"""
        if len(self.l1_cache) >= self.l1_max_size:
            # Remove item mais antigo (FIFO)
            oldest_key = next(iter(self.l1_cache))
            del self.l1_cache[oldest_key]

        self.l1_cache[key] = value

    def delete(self, key: str):
        """Remove valor de todas as camadas"""
        # L1
        if key in self.l1_cache:
            del self.l1_cache[key]

        # L2
        if redis_client.is_available:
            redis_client.delete(key)

    def clear_all(self):
        """Limpa todo o cache"""
        self.l1_cache.clear()
        if redis_client.is_available:
            redis_client.clear()

    def get_stats(self) -> dict:
        """Retorna estatísticas do cache"""
        total_requests = self.l1_hits + self.l2_hits + self.misses

        return {
            "l1_hits": self.l1_hits,
            "l2_hits": self.l2_hits,
            "l3_hits": self.l3_hits,
            "misses": self.misses,
            "total_requests": total_requests,
            "hit_rate": round((self.l1_hits + self.l2_hits) / total_requests * 100, 2) if total_requests > 0 else 0,
            "l1_size": len(self.l1_cache),
            "l1_max_size": self.l1_max_size,
        }


# Instância global
enterprise_cache = MultiLayerCache()


def cached(prefix: str, ttl: int = 300):
    """
    Decorator para cachear resultado de funções

    Args:
        prefix: Prefixo da chave de cache
        ttl: Time to live em segundos

    Example:
        @cached("store_details", ttl=600)
        def get_store_details(store_id: int):
            return db.query(Store).filter(Store.id == store_id).first()
    """

    def decorator(func: Callable):
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Gera chave única
            cache_key = enterprise_cache._generate_key(prefix, *args, **kwargs)

            # Tenta buscar no cache
            cached_value = enterprise_cache.get(cache_key)
            if cached_value is not None:
                return cached_value

            # Se não encontrou, executa função
            result = func(*args, **kwargs)

            # Armazena no cache
            enterprise_cache.set(cache_key, result, ttl)

            return result

        return wrapper

    return decorator