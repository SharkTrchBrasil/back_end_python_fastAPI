# src/core/cache/decorators.py

"""
Cache Decorators
================

Decorators para aplicar cache de forma declarativa em funções e rotas.

Uso:
    @cache(ttl=300, key_prefix="products")
    def get_products(store_id: int):
        return expensive_db_query()

Autor: PDVix Team
Data: 2025-01-18
"""

import logging
import hashlib
import json
from functools import wraps
from typing import Callable, Any, Optional

from src.core.cache.redis_client import redis_client

logger = logging.getLogger(__name__)


def cache(
        ttl: int = 300,
        key_prefix: str = "",
        key_builder: Optional[Callable] = None,
        skip_on_error: bool = True
):
    """
    ✅ Decorator para cachear resultado de funções

    Args:
        ttl: Tempo de vida em segundos (padrão: 5 minutos)
        key_prefix: Prefixo da chave (ex: "products", "dashboard")
        key_builder: Função customizada para gerar chave do cache
        skip_on_error: Se True, ignora erros e executa função normalmente

    Exemplo:
        @cache(ttl=300, key_prefix="store_products")
        def get_store_products(store_id: int):
            return db.query(Product).filter_by(store_id=store_id).all()

    A chave gerada será algo como:
        "store_products:store_id=123"
    """

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            # Se Redis não disponível, executa função diretamente
            if not redis_client.is_available:
                logger.debug(f"⚠️ Redis indisponível, executando {func.__name__} sem cache")
                return func(*args, **kwargs)

            try:
                # Gera chave do cache
                if key_builder:
                    cache_key = key_builder(*args, **kwargs)
                else:
                    cache_key = _default_key_builder(
                        func.__name__,
                        key_prefix,
                        args,
                        kwargs
                    )

                # Tenta buscar no cache
                cached_value = redis_client.get(cache_key)

                if cached_value is not None:
                    logger.debug(f"✅ CACHE HIT: {cache_key}")
                    return cached_value

                # Cache miss - executa função
                logger.debug(f"❌ CACHE MISS: {cache_key}")
                result = func(*args, **kwargs)

                # Armazena no cache
                redis_client.set(cache_key, result, ttl=ttl)

                return result

            except Exception as e:
                logger.error(f"❌ Erro no cache decorator: {e}")

                if skip_on_error:
                    logger.warning(f"⚠️ Executando {func.__name__} sem cache devido a erro")
                    return func(*args, **kwargs)
                else:
                    raise

        # Adiciona método para invalidar cache
        wrapper.invalidate = lambda *args, **kwargs: _invalidate_cache(
            func.__name__,
            key_prefix,
            args,
            kwargs
        )

        return wrapper

    return decorator


def _default_key_builder(
        func_name: str,
        prefix: str,
        args: tuple,
        kwargs: dict
) -> str:
    """
    ✅ Gerador padrão de chaves de cache

    Gera chave baseada em:
    - Nome da função
    - Prefixo (se fornecido)
    - Argumentos posicionais e nomeados

    Exemplo:
        get_products(123, limit=50) ->
        "products:get_products:args=(123,):kwargs={'limit':50}:hash=abc123"
    """
    # Serializa args e kwargs
    args_str = str(args)
    kwargs_str = json.dumps(kwargs, sort_keys=True, default=str)

    # Cria hash dos parâmetros (para evitar chaves muito longas)
    params_hash = hashlib.md5(
        f"{args_str}{kwargs_str}".encode()
    ).hexdigest()[:8]

    # Monta a chave
    parts = []

    if prefix:
        parts.append(prefix)

    parts.append(func_name)
    parts.append(params_hash)

    return ":".join(parts)


def _invalidate_cache(
        func_name: str,
        prefix: str,
        args: tuple,
        kwargs: dict
) -> int:
    """Invalida cache de uma função específica com parâmetros específicos"""
    cache_key = _default_key_builder(func_name, prefix, args, kwargs)
    return redis_client.delete(cache_key)


# ═══════════════════════════════════════════════════════════
# DECORATOR PARA FASTAPI ROUTES
# ═══════════════════════════════════════════════════════════

def cache_route(
        ttl: int = 300,
        key_builder: Optional[Callable] = None
):
    """
    ✅ Decorator específico para rotas FastAPI

    Automaticamente gera chave baseada em:
    - Path params
    - Query params
    - Request body (se necessário)

    Exemplo:
        @router.get("/products")
        @cache_route(ttl=300)
        def get_products(store_id: int, limit: int = 50):
            return {"products": [...]}
    """

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def async_wrapper(*args, **kwargs) -> Any:
            if not redis_client.is_available:
                if asyncio.iscoroutinefunction(func):
                    return await func(*args, **kwargs)
                return func(*args, **kwargs)

            try:
                # Gera chave customizada ou padrão
                if key_builder:
                    cache_key = key_builder(*args, **kwargs)
                else:
                    # Remove 'db' e 'request' dos kwargs para gerar chave limpa
                    clean_kwargs = {
                        k: v for k, v in kwargs.items()
                        if k not in ['db', 'request', 'background_tasks']
                    }
                    cache_key = _default_key_builder(
                        func.__name__,
                        "route",
                        args,
                        clean_kwargs
                    )

                # Busca no cache
                cached_value = redis_client.get(cache_key)

                if cached_value is not None:
                    logger.debug(f"✅ ROUTE CACHE HIT: {cache_key}")
                    return cached_value

                # Executa rota
                logger.debug(f"❌ ROUTE CACHE MISS: {cache_key}")

                if asyncio.iscoroutinefunction(func):
                    result = await func(*args, **kwargs)
                else:
                    result = func(*args, **kwargs)

                # Armazena no cache
                redis_client.set(cache_key, result, ttl=ttl)

                return result

            except Exception as e:
                logger.error(f"❌ Erro no route cache: {e}")

                if asyncio.iscoroutinefunction(func):
                    return await func(*args, **kwargs)
                return func(*args, **kwargs)

        @wraps(func)
        def sync_wrapper(*args, **kwargs) -> Any:
            # Mesma lógica para funções síncronas
            if not redis_client.is_available:
                return func(*args, **kwargs)

            try:
                if key_builder:
                    cache_key = key_builder(*args, **kwargs)
                else:
                    clean_kwargs = {
                        k: v for k, v in kwargs.items()
                        if k not in ['db', 'request', 'background_tasks']
                    }
                    cache_key = _default_key_builder(
                        func.__name__,
                        "route",
                        args,
                        clean_kwargs
                    )

                cached_value = redis_client.get(cache_key)

                if cached_value is not None:
                    logger.debug(f"✅ ROUTE CACHE HIT: {cache_key}")
                    return cached_value

                logger.debug(f"❌ ROUTE CACHE MISS: {cache_key}")
                result = func(*args, **kwargs)

                redis_client.set(cache_key, result, ttl=ttl)

                return result

            except Exception as e:
                logger.error(f"❌ Erro no route cache: {e}")
                return func(*args, **kwargs)

        # Retorna wrapper apropriado
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper

    return decorator


# ✅ IMPORT NECESSÁRIO
import asyncio