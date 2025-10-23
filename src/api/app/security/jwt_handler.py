# src/core/security/jwt_handler.py
import uuid

import jwt
from datetime import datetime, timedelta, timezone

from src.core.config import config
from src.core.security.security import SECRET_KEY


class MenuJWTHandler:
    SECRET_KEY = config.JWT_SECRET  # Do .env

    @staticmethod
    def create_access_token(store_id: int, store_url: str) -> dict:
        """Gera token JWT seguro para acesso ao cardápio"""
        now = datetime.now(timezone.utc)
        exp = now + timedelta(hours=24)

        payload = {
            "sub": f"menu:{store_id}",
            "store_id": store_id,
            "store_url": store_url,
            "type": "menu_access",
            "iat": int(now.timestamp()),
            "exp": int(exp.timestamp()),
            "jti": str(uuid.uuid4()),  # ID único
        }

        access_token = jwt.encode(payload, SECRET_KEY, algorithm="HS256")
        refresh_token = jwt.encode({...}, SECRET_KEY, algorithm="HS256")

        return {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "expires_in": 86400,  # 24h em segundos
            "token_type": "bearer"
        }