# src/api/admin/routes/auth.py

import uuid
from datetime import datetime, timezone
from typing import Annotated

import jwt
from fastapi import APIRouter, Depends, HTTPException, Body, Header
from fastapi.security import OAuth2PasswordRequestForm
from starlette import status
from starlette.requests import Request

from src.api.schemas.auth.auth import TokenResponse
from src.api.admin.utils.authenticate import authenticate_user
from src.api.schemas.auth.auth_totem import (
    TotemAuthorizationResponse,
    AuthenticateByUrlRequest,
    TotemCheckTokenResponse
)
from src.core import models
from src.core.config import config
from src.core.database import GetDBDep
from src.core.dependencies import GetCurrentUserDep
from src.api.schemas.auth.user import ChangePasswordData
from src.core.models import TotemAuthorization

# ✅ IMPORTAÇÃO CORRETA
from src.core.rate_limit.rate_limit import rate_limit, RATE_LIMITS, logger

from src.core.security.security import (
    create_access_token,
    create_refresh_token,
    verify_refresh_token,
    get_password_hash,
    ALGORITHM,
    SECRET_KEY
)

from src.core.security.token_blacklist import TokenBlacklist
from src.core.cache.redis_client import redis_client
from src.core.cache.keys import CacheKeys

router = APIRouter(prefix="/auth", tags=["Auth"])


@router.post("/login", response_model=TokenResponse)
@rate_limit(RATE_LIMITS["login"])  # ✅ Usa wrapper customizado
async def login_for_access_token(
        request: Request,
        db: GetDBDep,
        form_data: OAuth2PasswordRequestForm = Depends(),
):
    """
    ✅ LOGIN SEGURO COM RATE LIMITING
    """
    email = form_data.username

    # ═══════════════════════════════════════════════════════════
    # 1️⃣ PROTEÇÃO CONTRA BRUTE FORCE
    # ═══════════════════════════════════════════════════════════

    locked_key = CacheKeys.account_locked(email)
    if redis_client.exists(locked_key):
        logger.error(f"🔒 Conta bloqueada: {email}")
        raise HTTPException(
            status_code=429,
            detail="Conta temporariamente bloqueada. Tente em 15 minutos."
        )

    # ═══════════════════════════════════════════════════════════
    # 2️⃣ AUTENTICAÇÃO
    # ═══════════════════════════════════════════════════════════

    user: models.User | None = authenticate_user(db, email, form_data.password)

    if not user:
        failed_key = CacheKeys.login_failed_attempts(email)

        if redis_client._is_available and redis_client._client:
            attempts = redis_client._client.incr(failed_key)

            if attempts == 1:
                redis_client._client.expire(failed_key, 900)

            logger.warning(f"⚠️ Login falhou ({attempts}/5): {email}")

            if attempts >= 5:
                redis_client.set(locked_key, "locked", ttl=900)
                logger.error(f"🔒 Conta bloqueada: {email}")
                raise HTTPException(
                    status_code=429,
                    detail="Conta bloqueada após 5 tentativas."
                )

        raise HTTPException(
            status_code=401,
            detail="Email ou senha incorretos"
        )

    if not user.is_email_verified:
        raise HTTPException(status_code=401, detail="Email não verificado")

    if not user.is_active:
        raise HTTPException(status_code=401, detail="Conta inativa")

    # Limpa tentativas falhadas
    failed_key = CacheKeys.login_failed_attempts(email)
    redis_client.delete(failed_key)

    # ═══════════════════════════════════════════════════════════
    # 3️⃣ GERAÇÃO DE TOKENS
    # ═══════════════════════════════════════════════════════════

    access_jti = str(uuid.uuid4())
    refresh_jti = str(uuid.uuid4())

    access_token = create_access_token(
        data={"sub": user.email},
        jti=access_jti
    )
    refresh_token = create_refresh_token(
        data={"sub": user.email},
        jti=refresh_jti
    )

    TokenBlacklist.store_user_token(
        user.email,
        access_jti,
        config.ACCESS_TOKEN_EXPIRE_MINUTES * 60
    )
    TokenBlacklist.store_user_token(
        user.email,
        refresh_jti,
        config.REFRESH_TOKEN_EXPIRE_DAYS * 24 * 60 * 60
    )

    logger.info(f"✅ Login bem-sucedido: {email}")

    # ✅ RETORNA DICT NORMAL - FastAPI converte automaticamente
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "refresh_token": refresh_token
    }


@router.post("/refresh", response_model=TokenResponse)
@rate_limit("10/minute")
async def refresh_access_token(
        request: Request,
        refresh_token: Annotated[str, Body(..., embed=True)],
        db: GetDBDep
):
    """Renova access token usando refresh token"""
    payload = verify_refresh_token(refresh_token)

    if not payload:
        raise HTTPException(status_code=401, detail="Invalid refresh token")

    email = payload.get("sub")
    old_jti = payload.get("jti")

    user = db.query(models.User).filter(
        models.User.email == email,
        models.User.is_active == True
    ).first()

    if not user:
        raise HTTPException(status_code=401, detail="User not found")

    if old_jti:
        exp = payload.get("exp")
        now = datetime.now(timezone.utc).timestamp()
        ttl_seconds = int(exp - now) if exp else config.REFRESH_TOKEN_EXPIRE_DAYS * 24 * 60 * 60

        if ttl_seconds > 0:
            TokenBlacklist.add_token(old_jti, ttl_seconds)

    new_access_jti = str(uuid.uuid4())
    new_refresh_jti = str(uuid.uuid4())

    new_access_token = create_access_token(data={"sub": email}, jti=new_access_jti)
    new_refresh_token = create_refresh_token(data={"sub": email}, jti=new_refresh_jti)

    TokenBlacklist.store_user_token(email, new_access_jti, config.ACCESS_TOKEN_EXPIRE_MINUTES * 60)
    TokenBlacklist.store_user_token(email, new_refresh_jti, config.REFRESH_TOKEN_EXPIRE_DAYS * 24 * 60 * 60)

    return {
        "access_token": new_access_token,
        "token_type": "bearer",
        "refresh_token": new_refresh_token
    }


@router.post("/change-password")
@rate_limit(RATE_LIMITS["password_reset"])
async def change_password(
        request: Request,
        change_password_data: ChangePasswordData,
        db: GetDBDep,
        current_user: GetCurrentUserDep,
):
    """Troca senha do usuário"""
    user = authenticate_user(db, current_user.email, change_password_data.old_password)

    if not user:
        raise HTTPException(status_code=401, detail="Senha atual incorreta")

    user.hashed_password = get_password_hash(change_password_data.new_password)
    db.commit()

    TokenBlacklist.revoke_all_user_tokens(current_user.email)

    logger.warning(f"🔐 Senha alterada: {current_user.email}")

    return {
        "message": "Senha alterada. Faça login novamente."
    }


@router.post("/logout")
@rate_limit("10/minute")
async def logout(
        request: Request,
        current_user: GetCurrentUserDep,
        authorization: str = Header(...)
):
    """Logout - revoga token atual"""
    try:
        token = authorization.split(" ")[1] if " " in authorization else authorization
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM], options={"verify_signature": False})
        jti = payload.get("jti")
        exp = payload.get("exp")

        if jti and exp:
            now = datetime.now(timezone.utc).timestamp()
            ttl_seconds = int(exp - now)

            if ttl_seconds > 0:
                TokenBlacklist.add_token(jti, ttl_seconds)
                logger.info(f"✅ Token revogado: {jti[:8]}...")

        return {"message": "Logout realizado com sucesso"}

    except Exception as e:
        logger.error(f"❌ Erro no logout: {e}")
        return {"message": "Logout realizado com sucesso"}


@router.post("/logout-all")
@rate_limit("3/hour")
async def logout_all_devices(
        request: Request,
        current_user: GetCurrentUserDep
):
    """Logout global - revoga todos tokens"""
    try:
        TokenBlacklist.revoke_all_user_tokens(current_user.email)
        logger.warning(f"🚨 Logout global: {current_user.email}")
        return {"message": "Todos os dispositivos foram desconectados"}

    except Exception as e:
        logger.error(f"❌ Erro no logout global: {e}")
        raise HTTPException(status_code=500, detail="Erro ao desconectar dispositivos")


# ═══════════════════════════════════════════════════════════
# ENDPOINTS DE TOTEM (SEM ALTERAÇÃO)
# ═══════════════════════════════════════════════════════════

@router.post("/subdomain", response_model=TotemAuthorizationResponse)
def authenticate_by_url(db: GetDBDep, request_body: AuthenticateByUrlRequest):
    """Autenticação de totem por URL"""
    totem_auth = db.query(TotemAuthorization).filter(
        TotemAuthorization.store_url == request_body.store_url,
        TotemAuthorization.granted == True
    ).first()

    if not totem_auth:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Totem authorization not found or not granted for this URL."
        )

    totem_auth.sid = str(uuid.uuid4())
    totem_auth.updated_at = datetime.utcnow()
    db.add(totem_auth)
    db.commit()
    db.refresh(totem_auth)

    return totem_auth


@router.post("/check-token", response_model=TotemCheckTokenResponse)
def check_token(db: GetDBDep, totem_token: Annotated[str, Body(..., embed=True)]):
    """Verifica token de totem"""
    auth = db.query(models.TotemAuthorization).filter_by(
        totem_token=totem_token
    ).first()

    if not auth:
        raise HTTPException(status_code=404)

    return auth