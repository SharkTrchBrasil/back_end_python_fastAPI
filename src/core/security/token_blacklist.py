# src/core/token_blacklist.py

import redis
from datetime import timedelta
from src.core.config import config

# ✅ Conexão Redis
redis_client = redis.from_url(
    config.REDIS_URL or "redis://localhost:6379/1",
    decode_responses=True
)


class TokenBlacklist:
    """Sistema de blacklist para revogação de tokens JWT"""

    @staticmethod
    def add_token(jti: str, ttl_seconds: int):
        """
        Adiciona token à blacklist com TTL automático.

        Args:
            jti: ID único do token (JWT ID)
            ttl_seconds: Tempo até expiração natural do token
        """
        key = f"blacklist:{jti}"
        redis_client.setex(
            key,
            ttl_seconds,
            "revoked"
        )

    @staticmethod
    def is_blacklisted(jti: str) -> bool:
        """Verifica se token está na blacklist"""
        key = f"blacklist:{jti}"
        return redis_client.exists(key) > 0

    # ✅ CORREÇÃO: Usar SCAN ao invés de KEYS
    @staticmethod
    def revoke_all_user_tokens(user_email: str):
        """Revoga TODOS os tokens de um usuário de forma segura."""
        pattern = f"user_tokens:{user_email}:*"

        # ✅ SCAN não bloqueia o Redis
        cursor = 0
        while True:
            cursor, keys = redis_client.scan(
                cursor=cursor,
                match=pattern,
                count=100
            )

            if keys:
                for key in keys:
                    jti = key.split(":")[-1]
                    TokenBlacklist.add_token(jti, 30 * 24 * 60 * 60)

            if cursor == 0:
                break

    @staticmethod
    def store_user_token(user_email: str, jti: str, ttl_seconds: int):
        """
        Registra token ativo do usuário para possível revogação global.
        """
        key = f"user_tokens:{user_email}:{jti}"
        redis_client.setex(key, ttl_seconds, "active")