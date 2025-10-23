# src/core/cors/cors_middleware.py

"""
Middleware CORS customizado para validar subdomínios dinâmicos
Sistema Multi-Tenant MenuHub
"""
import re
import logging
import os
from typing import List

logger = logging.getLogger(__name__)

class CustomCORSMiddleware:
    """
    Middleware que valida subdomínios dinâmicos para sistema multi-tenant

    Exemplo de subdomínios válidos:
    - https://pizzaria123.menuhub.com.br (loja do cliente)
    - https://restaurante-abc.menuhub.com.br
    - http://localhost:* (APENAS EM DESENVOLVIMENTO)
    """

    # ✅ Padrão para validar subdomínios de lojas dos clientes (PRODUÇÃO)
    SUBDOMAIN_PATTERN = re.compile(
        r'^https://[\w\-]+\.menuhub\.com\.br$',
        re.IGNORECASE
    )

    # ✅ Padrão adicional para www
    WWW_PATTERN = re.compile(
        r'^https://www\.menuhub\.com\.br$',
        re.IGNORECASE
    )

    # ✅ NOVO: Padrões para DESENVOLVIMENTO LOCAL
    LOCALHOST_PATTERN = re.compile(
        r'^http://localhost:\d+$',
        re.IGNORECASE
    )

    LOCALHOST_IP_PATTERN = re.compile(
        r'^http://127\.0\.0\.1:\d+$',
        re.IGNORECASE
    )

    @classmethod
    def is_development_mode(cls) -> bool:
        """
        Verifica se está em modo de desenvolvimento
        """
        env = os.getenv('ENVIRONMENT', 'production').lower()
        return env in ['development', 'dev', 'local']

    @classmethod
    def is_allowed_origin(cls, origin: str, allowed_origins: List[str]) -> bool:
        """
        Valida se a origem é permitida

        Args:
            origin: Origem da requisição (ex: https://loja123.menuhub.com.br)
            allowed_origins: Lista de origens base permitidas

        Returns:
            True se a origem é válida, False caso contrário
        """

        if not origin:
            return False

        # 1. Verifica se está na lista explícita de origens permitidas
        if origin in allowed_origins:
            logger.debug(f"✅ Origem permitida (lista explícita): {origin}")
            return True

        # ✅ 2. NOVO: Permite localhost APENAS em desenvolvimento
        if cls.is_development_mode():
            if cls.LOCALHOST_PATTERN.match(origin) or cls.LOCALHOST_IP_PATTERN.match(origin):
                logger.info(f"🔧 [DEV] Origem localhost permitida: {origin}")
                return True

        # 3. Valida subdomínios dinâmicos (lojas dos clientes)
        if cls.SUBDOMAIN_PATTERN.match(origin):
            logger.debug(f"✅ Origem permitida (subdomínio válido): {origin}")
            return True

        # 4. Valida www
        if cls.WWW_PATTERN.match(origin):
            logger.debug(f"✅ Origem permitida (www): {origin}")
            return True

        # 5. Rejeita qualquer outra origem
        logger.warning(
            f"🚨 CORS BLOQUEADO: Origem não autorizada\n"
            f"   Origem rejeitada: {origin}\n"
            f"   Padrão esperado: https://*.menuhub.com.br\n"
            f"   Modo: {'DESENVOLVIMENTO' if cls.is_development_mode() else 'PRODUÇÃO'}"
        )
        return False

    @classmethod
    def get_cors_headers(cls, origin: str, allowed_origins: List[str]) -> dict:
        """
        Retorna headers CORS apropriados se a origem for válida
        """
        if cls.is_allowed_origin(origin, allowed_origins):
            return {
                "Access-Control-Allow-Origin": origin,
                "Access-Control-Allow-Credentials": "true",
                "Access-Control-Allow-Methods": "GET, POST, PUT, DELETE, PATCH, OPTIONS",
                "Access-Control-Allow-Headers": "Authorization, Content-Type, Accept, X-Store-ID, X-Device-ID",
                "Access-Control-Max-Age": "3600",  # Cache preflight por 1 hora
                "Access-Control-Expose-Headers": "X-Total-Count, X-Page-Number, X-Rate-Limit",
            }

        # Origem não autorizada - retorna headers vazios
        return {}

    @classmethod
    def extract_subdomain(cls, origin: str) -> str:
        """
        Extrai o subdomínio de uma URL

        Exemplo:
            https://pizzaria123.menuhub.com.br -> pizzaria123
            http://localhost:3000 -> localhost
        """
        # Produção: extrai subdomínio
        match = re.match(r'^https://([\w\-]+)\.menuhub\.com\.br$', origin)
        if match:
            return match.group(1)

        # Desenvolvimento: retorna 'localhost'
        if cls.is_development_mode():
            if cls.LOCALHOST_PATTERN.match(origin) or cls.LOCALHOST_IP_PATTERN.match(origin):
                return "localhost"

        return ""