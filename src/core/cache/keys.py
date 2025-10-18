# src/core/cache/keys.py

"""
Cache Keys Generator
====================

Gerador centralizado de chaves de cache com padrões consistentes.

Padrão de chaves:
- store:{store_id}:products:list
- store:{store_id}:categories:list
- store:{store_id}:product:{product_id}
- dashboard:{store_id}:{date_range}

Autor: PDVix Team
Data: 2025-01-18
"""

from datetime import date
from typing import Optional


class CacheKeys:
    """
    ✅ Gerador de chaves de cache com padrões consistentes

    Usar sempre esta classe para gerar chaves garante:
    - Invalidação eficiente
    - Organização
    - Fácil debugging
    """

    # ═══════════════════════════════════════════════════════════
    # PRODUTOS (APP - CARDÁPIO DIGITAL)
    # ═══════════════════════════════════════════════════════════

    @staticmethod
    def store_products_list(store_id: int) -> str:
        """Lista completa de produtos da loja (para app)"""
        return f"store:{store_id}:products:list"

    @staticmethod
    def store_categories_list(store_id: int) -> str:
        """Lista completa de categorias da loja (para app)"""
        return f"store:{store_id}:categories:list"

    @staticmethod
    def store_base_details(store_slug: str) -> str:
        """Detalhes básicos da loja por slug"""
        return f"store:slug:{store_slug}:details"

    @staticmethod
    def store_all_pattern(store_id: int) -> str:
        """Pattern para invalidar TUDO de uma loja"""
        return f"store:{store_id}:*"

    # ═══════════════════════════════════════════════════════════
    # DASHBOARD & ANALYTICS (ADMIN)
    # ═══════════════════════════════════════════════════════════

    @staticmethod
    def dashboard_data(
            store_id: int,
            start_date: date,
            end_date: date
    ) -> str:
        """Dados do dashboard para período específico"""
        return f"dashboard:{store_id}:{start_date}:{end_date}"

    @staticmethod
    def performance_data(
            store_id: int,
            start_date: date,
            end_date: date
    ) -> str:
        """Dados de performance para período específico"""
        return f"performance:{store_id}:{start_date}:{end_date}"

    @staticmethod
    def dashboard_pattern(store_id: int) -> str:
        """Pattern para invalidar todos dashboards da loja"""
        return f"dashboard:{store_id}:*"

    @staticmethod
    def performance_pattern(store_id: int) -> str:
        """Pattern para invalidar toda performance da loja"""
        return f"performance:{store_id}:*"

    # ═══════════════════════════════════════════════════════════
    # PRODUTOS (ADMIN)
    # ═══════════════════════════════════════════════════════════

    @staticmethod
    def admin_products_list(
            store_id: int,
            skip: int = 0,
            limit: int = 50
    ) -> str:
        """Lista de produtos no admin com paginação"""
        return f"admin:{store_id}:products:list:{skip}:{limit}"

    @staticmethod
    def admin_products_pattern(store_id: int) -> str:
        """Pattern para invalidar todas listas de produtos do admin"""
        return f"admin:{store_id}:products:*"

    # ═══════════════════════════════════════════════════════════
    # ANALYTICS
    # ═══════════════════════════════════════════════════════════

    @staticmethod
    def customer_analytics(store_id: int, days: int = 30) -> str:
        """Analytics de clientes"""
        return f"analytics:{store_id}:customers:{days}d"

    @staticmethod
    def product_analytics(store_id: int, days: int = 30) -> str:
        """Analytics de produtos"""
        return f"analytics:{store_id}:products:{days}d"

    @staticmethod
    def analytics_pattern(store_id: int) -> str:
        """Pattern para invalidar todos analytics"""
        return f"analytics:{store_id}:*"