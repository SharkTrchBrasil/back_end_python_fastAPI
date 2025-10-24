# src/api/app/routes/auth.py
import re
from logging import getLogger
from fastapi import APIRouter, Body, HTTPException
from starlette.requests import Request
# --- ✅ CORREÇÃO: Importar JSONResponse ---
from starlette.responses import JSONResponse

from src.api.app.security.domain_validator import DomainValidator
from src.api.app.security.jwt_handler import MenuJWTHandler
from src.api.app.services.authorize_totem import TotemAuthorizationService
from src.api.app.services.connection_token_service import ConnectionTokenService
from src.api.schemas.auth.auth_totem import AuthenticateByUrlRequest, SecureMenuAuthResponse
from src.core.database import GetDBDep
from src.core.models import TotemAuthorization, AuditLog
from src.core.rate_limit.rate_limit import limiter

logger = getLogger(__name__)
router = APIRouter(tags=["Totem Auth"], prefix="/auth")


@router.post("/subdomain")
@limiter.limit("10/minute")
async def authenticate_menu_access(
        request: Request,
        db: GetDBDep,
        body: AuthenticateByUrlRequest
):
    """
    🔒 Endpoint seguro para autenticação de cardápio.
    1. Valida o totem_token persistente.
    2. Gera e retorna um `connection_token` de uso único para o WebSocket.
    3. Gera e retorna os tokens JWT para autenticação do cliente logado.
    """
    # 1. Autoriza o totem ou cria uma nova autorização
    totem_auth = TotemAuthorizationService.authorize_or_create(
        db, store_url=body.store_url, totem_token=body.totem_token
    )

    if not totem_auth or not totem_auth.store:
        logger.warning(f"🚨 Tentativa de acesso falhou para loja: {body.store_url}")
        raise HTTPException(404, "Loja não encontrada ou totem não configurado.")

    # 2. Valida a origem da requisição (CORS)
    origin = request.headers.get("origin")
    if not DomainValidator.is_allowed_origin(origin, totem_auth.store):
        logger.warning(f"🚨 Acesso bloqueado de origem não autorizada: {origin}")
        raise HTTPException(403, "Origem não autorizada")

    # 3. Gera o token de conexão de uso único para o Socket.IO
    connection_token = ConnectionTokenService.generate_token(db, totem_auth_id=totem_auth.id)

    # 4. Gera os tokens JWT para autenticação do cliente (uso posterior)
    jwt_tokens = MenuJWTHandler.create_access_token(
        store_id=totem_auth.store_id,
        store_url=totem_auth.store_url
    )

    # 5. Registra o log de auditoria
    db.add(AuditLog(
        store_id=totem_auth.store_id, action="menu_auth_request",
        description=f"Solicitação de acesso ao cardápio de {totem_auth.store_url}",
        ip_address=request.client.host
    ))
    db.commit()

    # 6. Retorna todos os tokens necessários para o cliente
    response_data = {
        **jwt_tokens,
        "connection_token": connection_token,  # ✅ O token crucial para o Socket.IO
        "store_id": totem_auth.store_id,
        "store_url": totem_auth.store_url,
        "store_name": totem_auth.store.name,
    }

    return JSONResponse(content=response_data)