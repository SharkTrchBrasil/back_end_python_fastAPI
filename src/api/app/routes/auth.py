# src/api/app/routes/auth.py
import re
from typing import Annotated

from fastapi import APIRouter, Body, HTTPException
from starlette.requests import Request

from src.api.app.security.domain_validator import DomainValidator
from src.api.app.security.jwt_handler import MenuJWTHandler
from src.api.schemas.auth.auth_totem import (
    AuthenticateByUrlRequest, SecureMenuAuthResponse
)
from src.core.database import GetDBDep
from src.core.models import TotemAuthorization, AuditLog
from src.core.rate_limit.rate_limit import limiter
from logging import getLogger

logger = getLogger(__name__)
router = APIRouter(tags=["Totem Auth"], prefix="/auth")

@router.post("/subdomain", response_model=SecureMenuAuthResponse)
@limiter.limit("10/minute")
async def authenticate_menu_access(
        request: Request,
        db: GetDBDep,
        body: AuthenticateByUrlRequest
):
    """
    🔒 Endpoint seguro para autenticação de cardápio via subdomínio.
    """
    # 1. Sanitiza e valida input
    store_url = body.store_url.strip().lower()
    if not re.match(r'^[a-z0-9-]{3,50}$', store_url):
        raise HTTPException(400, "URL da loja inválida")

    # 2. Busca loja no banco
    totem_auth = db.query(TotemAuthorization).filter(
        TotemAuthorization.store_url == store_url,
        TotemAuthorization.granted == True
    ).first()

    if not totem_auth or not totem_auth.store:
        logger.warning(
            f"🚨 Tentativa de acesso a loja inexistente ou não associada: {store_url} "
            f"de {request.client.host}"
        )
        raise HTTPException(404, "Loja não encontrada ou não configurada.")

    # 3. Valida origem da requisição
    origin = request.headers.get("origin")
    if not DomainValidator.is_allowed_origin(origin, totem_auth.store):
        logger.warning(
            f"🚨 Acesso bloqueado de origem não autorizada: {origin} "
            f"para loja {store_url}"
        )
        raise HTTPException(403, "Origem não autorizada")

    # 4. Gera tokens JWT
    tokens = MenuJWTHandler.create_access_token(
        store_id=totem_auth.store_id,
        store_url=store_url
    )

    # 5. Registra acesso em log de auditoria
    db.add(AuditLog(
        store_id=totem_auth.store_id,
        action="menu_access",
        entity_type="totem_auth",
        description=f"Acesso ao cardápio de {store_url}",
        ip_address=request.client.host,
        user_agent=request.headers.get("user-agent"),
        metadata={"origin": origin}
    ))
    db.commit()

    return {
        **tokens,
        "store_id": totem_auth.store_id,
        "store_url": store_url,
        "store_name": totem_auth.store.name,
    }