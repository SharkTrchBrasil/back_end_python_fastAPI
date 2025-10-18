# src/core/cache/cache_manager.py

"""
Cache Manager
=============

Gerenciador de alto nível para operações de cache com invalidação inteligente.

Autor: PDVix Team
Data: 2025-01-18
"""

import logging
from typing import Any, Optional, Callable
from functools import wraps

from src.core.cache.redis_client import redis_client
from src.core.cache.keys import CacheKeys

logger = logging.getLogger(__name__)


class CacheManager:
    """
    ✅ Gerenciador de cache com invalidação inteligente

    Fornece métodos de alto nível para:
    - Invalidação por loja
    - Invalidação por tipo de dado
    - Invalidação em cascata
    """

    def __init__(self):
        self.client = redis_client
        self.keys = CacheKeys()

    # ═══════════════════════════════════════════════════════════
    # INVALIDAÇÃO POR TIPO
    # ═══════════════════════════════════════════════════════════

    def invalidate_store_products(self, store_id: int) -> int:
        """
        ✅ Invalida cache de produtos de uma loja

        Invalida:
        - Lista de produtos (app)
        - Lista de produtos (admin)
        - Categorias (que contêm produtos)

        Returns:
            Número de chaves removidas
        """
        patterns = [
            self.keys.store_products_list(store_id),
            self.keys.store_categories_list(store_id),
            self.keys.admin_products_pattern(store_id),
        ]

        total = 0
        for pattern in patterns:
            if "*" in pattern:
                total += self.client.delete_pattern(pattern)
            else:
                total += self.client.delete(pattern)

        logger.info(f"🗑️ Invalidado cache de produtos da loja {store_id}: {total} chaves")
        return total

    def invalidate_store_analytics(self, store_id: int) -> int:
        """
        ✅ Invalida cache de analytics de uma loja

        Invalida:
        - Dashboard
        - Performance
        - Customer analytics
        - Product analytics
        """
        patterns = [
            self.keys.dashboard_pattern(store_id),
            self.keys.performance_pattern(store_id),
            self.keys.analytics_pattern(store_id),
        ]

        total = 0
        for pattern in patterns:
            total += self.client.delete_pattern(pattern)

        logger.info(f"📊 Invalidado cache de analytics da loja {store_id}: {total} chaves")
        return total

    def invalidate_store_all(self, store_id: int) -> int:
        """
        ⚠️ Invalida TODO o cache de uma loja

        Use quando:
        - Loja alterou configurações globais
        - Importação em massa de produtos
        - Reset completo necessário
        """
        pattern = self.keys.store_all_pattern(store_id)
        total = self.client.delete_pattern(pattern)

        logger.warning(f"🗑️ Invalidado TODO cache da loja {store_id}: {total} chaves")
        return total

    # ═══════════════════════════════════════════════════════════
    # TRIGGERS DE INVALIDAÇÃO
    # ═══════════════════════════════════════════════════════════

    def on_product_change(self, store_id: int):
        """
        ✅ Trigger quando produtos são alterados

        Chamado quando:
        - Produto criado/editado/deletado
        - Preço alterado
        - Status alterado
        - Categoria alterada
        """
        self.invalidate_store_products(store_id)
        # Analytics também devem ser invalidados
        self.invalidate_store_analytics(store_id)

    def on_order_completed(self, store_id: int):
        """
        ✅ Trigger quando pedido é concluído

        Invalida apenas analytics (produtos não mudam)
        """
        self.invalidate_store_analytics(store_id)

    def on_category_change(self, store_id: int):
        """
        ✅ Trigger quando categorias são alteradas
        """
        self.invalidate_store_products(store_id)

    # ═══════════════════════════════════════════════════════════
    # ESTATÍSTICAS
    # ═══════════════════════════════════════════════════════════

    def get_stats(self) -> dict:
        """Retorna estatísticas do cache"""
        return self.client.get_stats()



    def invalidate_store_orders(self, store_id: int) -> int:
        """
        ✅ Invalida cache de pedidos de uma loja

        Invalida:
        - Lista de pedidos ativos (Socket.IO)
        - Lista paginada de pedidos
        - Detalhes individuais de pedidos
        """
        pattern = self.keys.admin_orders_pattern(store_id)
        total = self.client.delete_pattern(pattern)

        logger.info(f"🗑️ Invalidado cache de pedidos da loja {store_id}: {total} chaves")
        return total

    def on_order_status_change(self, store_id: int, order_id: int):
        """
        ✅ Trigger quando status de pedido muda

        Chamado quando:
        - Admin muda status via Socket.IO
        - Pedido criado
        - Pedido cancelado
        - Pedido entregue
        """
        # Invalida apenas o necessário
        keys_to_delete = [
            self.keys.admin_orders_active(store_id),
            self.keys.admin_order_details(store_id, order_id),
        ]

        # Também invalida lista paginada (todas as páginas)
        self.client.delete_pattern(f"admin:{store_id}:orders:list:*")

        total = self.client.delete(*keys_to_delete)
        logger.info(f"🗑️ Invalidado cache de pedido {order_id} (loja {store_id}): {total} chaves")


# ✅ INSTÂNCIA GLOBAL
cache_manager = CacheManager()