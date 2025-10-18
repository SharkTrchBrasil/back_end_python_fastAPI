# src/core/utils/input_sanitizer.py

import re
from typing import Optional


def sanitize_search_input(search: str, max_length: int = 100) -> str:
    """
    ✅ Sanitiza input de busca para prevenir SQL Injection

    Args:
        search: String de busca do usuário
        max_length: Tamanho máximo permitido

    Returns:
        String sanitizada segura
    """
    if not search:
        return ""

    # Remove espaços extras e limita tamanho
    search = search.strip()[:max_length]

    # Remove caracteres perigosos
    dangerous_patterns = [
        r"'", r'"', r'--', r'/\*', r'\*/', r';', r'\\',
        r'\bOR\b', r'\bAND\b', r'\bUNION\b', r'\bSELECT\b',
        r'\bDROP\b', r'\bDELETE\b', r'\bUPDATE\b', r'\bINSERT\b'
    ]

    for pattern in dangerous_patterns:
        if re.search(pattern, search, re.IGNORECASE):
            # Remove padrão perigoso
            search = re.sub(pattern, '', search, flags=re.IGNORECASE)

    # Permite apenas caracteres seguros
    search = re.sub(r'[^\w\s@.\-]', '', search)

    # Remove espaços duplicados
    search = re.sub(r'\s+', ' ', search).strip()

    return search