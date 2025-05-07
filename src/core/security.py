# core/security.py
# import secrets
#
# def generate_verification_token() -> str:
#     return secrets.token_urlsafe(32)

import random

def generate_verification_code() -> str:
    """Gera um código de 6 dígitos para verificação por e-mail."""
    return f"{random.randint(100000, 999999)}"
