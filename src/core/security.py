# core/security.py
import secrets

def generate_verification_token() -> str:
    return secrets.token_urlsafe(32)
