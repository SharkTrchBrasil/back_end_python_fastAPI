# src/core/security/jwt_handler.py
import uuid
from datetime import datetime, timedelta, timezone
import jwt
from src.core.config import config
from src.core.security.security import SECRET_KEY


class MenuJWTHandler:
    SECRET_KEY = config.SECRET_KEY

    @staticmethod
    def create_access_token(store_id: int, store_url: str) -> dict:
        """Gera tokens JWT seguros (access e refresh) para acesso ao cardápio."""
        now = datetime.now(timezone.utc)

        # --- PAYLOAD PARA O ACCESS TOKEN (curta duração) ---
        access_exp = now + timedelta(minutes=config.ACCESS_TOKEN_EXPIRE_MINUTES)
        access_payload = {
            "sub": f"menu:{store_id}",
            "store_id": store_id,
            "store_url": store_url,
            "scope": "menu_access",  # Escopo para acessar o cardápio
            "iat": now,
            "exp": access_exp,
            "jti": str(uuid.uuid4()),
        }

        # --- ✅ CORREÇÃO: PAYLOAD COMPLETO PARA O REFRESH TOKEN (longa duração) ---
        refresh_exp = now + timedelta(days=7)  # Duração de 7 dias
        refresh_payload = {
            "sub": f"menu:{store_id}",
            "scope": "refresh_menu",  # Escopo específico para renovar o token
            "iat": now,
            "exp": refresh_exp,
            "jti": str(uuid.uuid4()),
        }

        access_token = jwt.encode(access_payload, SECRET_KEY, algorithm="HS256")
        refresh_token = jwt.encode(refresh_payload, SECRET_KEY, algorithm="HS256")

        return {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "expires_in": int(timedelta(minutes=config.ACCESS_TOKEN_EXPIRE_MINUTES).total_seconds()),
            "token_type": "bearer"
        }