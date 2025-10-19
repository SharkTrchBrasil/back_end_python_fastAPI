# src/core/cors/cors_config.py
"""
Configuração CORS - Wrapper para config.py
==========================================

Este arquivo agora é apenas um wrapper para manter compatibilidade
com código existente. Toda a lógica real está em config.py

Autor: PDVix Team
Última atualização: 2025-01-19
"""

from src.core.config import config


def get_allowed_origins() -> list[str]:
    """
    ✅ Retorna lista de origens permitidas para CORS

    Delegado para config.get_allowed_origins_list()
    """
    return config.get_allowed_origins_list()


def get_allowed_methods() -> list[str]:
    """
    ✅ Retorna métodos HTTP permitidos

    Delegado para config.get_allowed_methods()
    """
    return config.get_allowed_methods()


def get_allowed_headers() -> list[str]:
    """
    ✅ Retorna headers permitidos

    Delegado para config.get_allowed_headers()
    """
    return config.get_allowed_headers()


def get_expose_headers() -> list[str]:
    """
    ✅ Retorna headers expostos

    Delegado para config.get_expose_headers()
    """
    return config.get_expose_headers()