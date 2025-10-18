# src/core/cache/redis_client.py

"""
Redis Client Singleton
======================

Cliente Redis centralizado com pool de conexões e tratamento de erros.

Características:
- ✅ Singleton pattern (uma única instância)
- ✅ Connection pooling
- ✅ Fallback gracioso (se Redis não disponível)
- ✅ Retry automático
- ✅ Logging detalhado

Autor: PDVix Team
Data: 2025-01-18
"""

import json
import logging
from typing import Any, Optional
from functools import wraps

import redis
from redis.connection import ConnectionPool
from redis.exceptions import RedisError, ConnectionError as RedisConnectionError

from src.core.config import config

logger = logging.getLogger(__name__)


class RedisClient:
    """
    ✅ Cliente Redis Singleton com fallback gracioso

    Se o Redis não estiver disponível, os métodos retornam None
    sem quebrar a aplicação.
    """

    _instance: Optional["RedisClient"] = None
    _client: Optional[redis.Redis] = None
    _is_available: bool = False

    def __new__(cls):
        """Garante que só existe uma instância (Singleton)"""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        """Inicializa conexão com Redis se ainda não foi feito"""
        if self._client is None:
            self._connect()

    def _connect(self):
        """
        ✅ Estabelece conexão com Redis

        Se falhar, marca como indisponível mas NÃO quebra a aplicação
        """
        if not config.REDIS_URL:
            logger.warning(
                "⚠️ REDIS_URL não configurado. Cache desabilitado. "
                "Configure REDIS_URL no .env para habilitar cache."
            )
            self._is_available = False
            return

        try:
            # Cria pool de conexões
            pool = ConnectionPool.from_url(
                config.REDIS_URL,
                max_connections=10,
                decode_responses=True,
                socket_timeout=5,
                socket_connect_timeout=5,
                retry_on_timeout=True
            )

            self._client = redis.Redis(connection_pool=pool)

            # Testa conexão
            self._client.ping()

            self._is_available = True
            logger.info("✅ Redis conectado com sucesso!")
            logger.info(f"   URL: {config.REDIS_URL.split('@')[-1]}")  # Oculta credenciais

        except (RedisError, RedisConnectionError) as e:
            logger.error(f"❌ Erro ao conectar no Redis: {e}")
            logger.warning("⚠️ Aplicação continuará sem cache")
            self._is_available = False
            self._client = None

    @property
    def is_available(self) -> bool:
        """Verifica se Redis está disponível"""
        return self._is_available

    def get(self, key: str) -> Optional[Any]:
        """
        ✅ Busca valor no cache

        Args:
            key: Chave do cache

        Returns:
            Valor deserializado ou None se não encontrado
        """
        if not self._is_available or not self._client:
            return None

        try:
            value = self._client.get(key)
            if value:
                # Deserializa JSON
                return json.loads(value)
            return None
        except (RedisError, json.JSONDecodeError) as e:
            logger.error(f"❌ Erro ao buscar chave '{key}': {e}")
            return None

    def set(
            self,
            key: str,
            value: Any,
            ttl: int = 300
    ) -> bool:
        """
        ✅ Armazena valor no cache

        Args:
            key: Chave do cache
            value: Valor a ser armazenado (será serializado em JSON)
            ttl: Tempo de vida em segundos (padrão: 5 minutos)

        Returns:
            True se sucesso, False se falhou
        """
        if not self._is_available or not self._client:
            return False

        try:
            # Serializa para JSON
            serialized = json.dumps(value, default=str)

            # Armazena com TTL
            self._client.setex(key, ttl, serialized)

            logger.debug(f"✅ Cache SET: {key} (TTL: {ttl}s)")
            return True

        except (RedisError, TypeError, ValueError) as e:
            logger.error(f"❌ Erro ao armazenar chave '{key}': {e}")
            return False

    def delete(self, *keys: str) -> int:
        """
        ✅ Remove uma ou mais chaves do cache

        Args:
            *keys: Chaves a serem removidas

        Returns:
            Número de chaves removidas
        """
        if not self._is_available or not self._client or not keys:
            return 0

        try:
            count = self._client.delete(*keys)
            logger.debug(f"🗑️ Cache DELETE: {count} chaves removidas")
            return count
        except RedisError as e:
            logger.error(f"❌ Erro ao deletar chaves: {e}")
            return 0

    def delete_pattern(self, pattern: str) -> int:
        """
        ✅ Remove todas as chaves que correspondem ao pattern

        Args:
            pattern: Pattern com wildcards (ex: "store:123:*")

        Returns:
            Número de chaves removidas
        """
        if not self._is_available or not self._client:
            return 0

        try:
            # Busca todas as chaves que correspondem
            keys = self._client.keys(pattern)

            if keys:
                count = self._client.delete(*keys)
                logger.debug(f"🗑️ Cache DELETE PATTERN '{pattern}': {count} chaves")
                return count

            return 0

        except RedisError as e:
            logger.error(f"❌ Erro ao deletar pattern '{pattern}': {e}")
            return 0

    def exists(self, key: str) -> bool:
        """Verifica se uma chave existe no cache"""
        if not self._is_available or not self._client:
            return False

        try:
            return bool(self._client.exists(key))
        except RedisError:
            return False

    def ttl(self, key: str) -> int:
        """
        Retorna o TTL restante de uma chave em segundos

        Returns:
            Segundos restantes, -1 se sem TTL, -2 se não existe
        """
        if not self._is_available or not self._client:
            return -2

        try:
            return self._client.ttl(key)
        except RedisError:
            return -2

    def flush_all(self) -> bool:
        """
        ⚠️ CUIDADO: Remove TODAS as chaves do Redis

        Use apenas em desenvolvimento/testes!
        """
        if not self._is_available or not self._client:
            return False

        if config.is_production:
            logger.error("❌ flush_all() bloqueado em produção!")
            return False

        try:
            self._client.flushdb()
            logger.warning("⚠️ Cache completamente limpo (flushdb)")
            return True
        except RedisError as e:
            logger.error(f"❌ Erro ao limpar cache: {e}")
            return False

    def get_stats(self) -> dict:
        """
        ✅ Retorna estatísticas do Redis

        Returns:
            Dict com informações de uso
        """
        if not self._is_available or not self._client:
            return {"available": False}

        try:
            info = self._client.info()
            return {
                "available": True,
                "used_memory_human": info.get("used_memory_human"),
                "connected_clients": info.get("connected_clients"),
                "total_commands_processed": info.get("total_commands_processed"),
                "keyspace_hits": info.get("keyspace_hits", 0),
                "keyspace_misses": info.get("keyspace_misses", 0),
                "hit_rate": self._calculate_hit_rate(info)
            }
        except RedisError as e:
            logger.error(f"❌ Erro ao buscar stats: {e}")
            return {"available": False, "error": str(e)}

    def _calculate_hit_rate(self, info: dict) -> float:
        """Calcula taxa de acerto do cache"""
        hits = info.get("keyspace_hits", 0)
        misses = info.get("keyspace_misses", 0)
        total = hits + misses

        if total == 0:
            return 0.0

        return round((hits / total) * 100, 2)


# ✅ INSTÂNCIA GLOBAL (Singleton)
redis_client = RedisClient()