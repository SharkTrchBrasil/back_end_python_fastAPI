# src/api/middleware/menu_auth_middleware.py
import jwt
from starlette.requests import Request
from starlette.responses import JSONResponse

from src.api.app.security.jwt_handler import MenuJWTHandler


async def verify_menu_token(request: Request, call_next):
    """Valida JWT em todas as requisições do cardápio"""

    # Rotas públicas (não precisam de token)
    if request.url.path in ["/app/auth/subdomain", "/health"]:
        return await call_next(request)

    # Extrai token
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        return JSONResponse(
            status_code=401,
            content={"error": "Token ausente"}
        )

    token = auth_header.split(" ")[1]

    try:
        # Valida e decodifica token
        payload = jwt.decode(
            token,
            MenuJWTHandler.SECRET_KEY,
            algorithms=["HS256"]
        )

        # Adiciona dados da loja ao request
        request.state.store_id = payload["store_id"]
        request.state.store_url = payload["store_url"]

    except jwt.ExpiredSignatureError:
        return JSONResponse(
            status_code=401,
            content={"error": "Token expirado", "code": "TOKEN_EXPIRED"}
        )
    except jwt.InvalidTokenError:
        return JSONResponse(
            status_code=401,
            content={"error": "Token inválido"}
        )

    return await call_next(request)