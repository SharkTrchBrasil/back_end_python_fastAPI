# src/core/cache/keys.py

"""
Cache Keys Generator
====================

Gerador centralizado de chaves de cache com padrões consistentes.

Padrão de chaves:
- store:{store_id}:products:list
- store:{store_id}:categories:list
- auth:login_failed:{email}
- auth:user_locations:{email}

Autor: PDVix Team
Data: 2025-01-19
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
    # AUTENTICAÇÃO & SEGURANÇA (NOVO)
    # ═══════════════════════════════════════════════════════════

    @staticmethod
    def login_failed_attempts(email: str) -> str:
        """
        Contador de tentativas de login falhadas

        TTL: 15 minutos
        Uso: Prevenir brute force
        """
        return f"auth:login_failed:{email}"

    @staticmethod
    def user_locations(email: str) -> str:
        """
        Set de países onde o usuário já fez login

        TTL: Sem expiração (permanente)
        Uso: Detectar login de localização suspeita
        """
        return f"auth:user_locations:{email}"

    @staticmethod
    def user_sessions(email: str) -> str:
        """
        Lista de sessões ativas do usuário

        TTL: 30 dias (mesmo do refresh token)
        Uso: Logout de todos dispositivos
        """
        return f"auth:user_sessions:{email}"

    @staticmethod
    def account_locked(email: str) -> str:
        """
        Flag de conta temporariamente bloqueada

        TTL: 1 hora
        Uso: Bloquear conta após muitas tentativas
        """
        return f"auth:account_locked:{email}"

    @staticmethod
    def password_reset_token(email: str) -> str:
        """
        Token de reset de senha

        TTL: 30 minutos
        Uso: Recuperação de senha
        """
        return f"auth:password_reset:{email}"

    @staticmethod
    def suspicious_login_alert(email: str) -> str:
        """
        Flag de alerta de login suspeito enviado

        TTL: 24 horas
        Uso: Evitar spam de alertas
        """
        return f"auth:suspicious_alert:{email}"

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

    # ═══════════════════════════════════════════════════════════
    # ORDERS (ADMIN) - TEMPO REAL
    # ═══════════════════════════════════════════════════════════

    @staticmethod
    def admin_orders_active(store_id: int) -> str:
        """Lista de pedidos ativos (para Socket.IO)"""
        return f"admin:{store_id}:orders:active"

    @staticmethod
    def admin_order_details(store_id: int, order_id: int) -> str:
        """Detalhes de um pedido específico"""
        return f"admin:{store_id}:order:{order_id}:details"

    @staticmethod
    def admin_orders_list(
            store_id: int,
            page: int,
            size: int,
            status: Optional[str] = None
    ) -> str:
        """Lista paginada de pedidos"""
        status_key = status or "all"
        return f"admin:{store_id}:orders:list:{page}:{size}:{status_key}"

    @staticmethod
    def admin_orders_pattern(store_id: int) -> str:
        """Pattern para invalidar TODOS pedidos de uma loja"""
        return f"admin:{store_id}:orders:*"