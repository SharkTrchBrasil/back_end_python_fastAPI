import re
import uuid
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Body, HTTPException, logger

from starlette import status
from starlette.requests import Request
from starlette.responses import Response

from src.api.app.security.domain_validator import DomainValidator
from src.api.app.security.jwt_handler import MenuJWTHandler
from src.api.schemas.auth.auth_totem import TotemAuth, TotemAuthorizationResponse, TotemCheckTokenResponse, \
    AuthenticateByUrlRequest, SecureMenuAuthResponse
from src.core import models
from src.core.config import config
from src.core.database import GetDBDep
from src.core.models import TotemAuthorization, AuditLog
from src.core.rate_limit.rate_limit import limiter

router = APIRouter(tags=["Totem Auth"], prefix="/auth")




@router.post("/subdomain", response_model=SecureMenuAuthResponse)
@limiter.limit("10/minute")  # Rate limit específico
async def authenticate_menu_access(
        request: Request,
        db: GetDBDep,
        body: AuthenticateByUrlRequest
):
    """
    🔒 Endpoint seguro para autenticação de cardápio
    """
    # 1. Sanitiza e valida input
    store_url = body.store_url.strip().lower()
    if not re.match(r'^[a-z0-9-]{3,50}$', store_url):
        raise HTTPException(400, "URL da loja inválida")

    # 2. Busca loja no banco
    totem_auth = db.query(TotemAuthorization).filter(
        TotemAuthorization.store_url == store_url,
        TotemAuthorization.granted == True  # Apenas autorizadas
    ).first()

    if not totem_auth:
        # ✅ Log de tentativa de acesso não autorizado
        logger.warning(
            f"🚨 Tentativa de acesso a loja inexistente: {store_url} "
            f"de {request.client.host}"
        )
        raise HTTPException(404, "Loja não encontrada")

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
    audit_log = AuditLog(
        store_id=totem_auth.store_id,
        action="menu_access",
        entity_type="totem_auth",
        description=f"Acesso ao cardápio de {store_url}",
        ip_address=request.client.host,
        user_agent=request.headers.get("user-agent"),
        metadata={"origin": origin}
    )
    db.add(audit_log)
    db.commit()

    return {
        **tokens,
        "store_id": totem_auth.store_id,
        "store_url": store_url,
        "store_name": totem_auth.store.name,
    }

@router.post("/start", response_model=TotemCheckTokenResponse)
def start_auth(
    db: GetDBDep,
    totem_auth: TotemAuth,
):
    auth = db.query(models.TotemAuthorization).filter_by(
        totem_token=totem_auth.totem_token
    ).first()

    if auth:
        auth.totem_name = totem_auth.totem_name
    else:
        auth = models.TotemAuthorization(**totem_auth.model_dump(), public_key=uuid.uuid4())
        db.add(auth)

    db.commit()
    return auth

@router.post("/check-token", response_model=TotemCheckTokenResponse)
def check_token(
    db: GetDBDep,
    totem_token: Annotated[str, Body(..., embed=True)]
):
    auth = db.query(models.TotemAuthorization).filter_by(
        totem_token=totem_token
    ).first()

    if not auth:
        raise HTTPException(status_code=404)

    return auth





