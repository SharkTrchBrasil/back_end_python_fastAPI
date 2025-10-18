import uuid
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Body
from fastapi.security import OAuth2PasswordRequestForm
from starlette import status
from starlette.requests import Request

from src.api.schemas.auth.auth import TokenResponse
from src.api.admin.utils.auth import authenticate_user
from src.api.schemas.auth.auth_totem import TotemAuthorizationResponse, AuthenticateByUrlRequest, TotemCheckTokenResponse
from src.core import models
from src.core.database import GetDBDep
from src.core.dependencies import GetCurrentUserDep
from src.api.schemas.auth.user import ChangePasswordData
from src.core.models import TotemAuthorization
from src.core.rate_limit.rate_limit import RATE_LIMITS, limiter, logger
# ✅ Funções de criação de token importadas
from src.core.security import create_access_token, create_refresh_token, verify_refresh_token, get_password_hash

router = APIRouter(prefix="/auth", tags=["Auth"])


@router.post("/login", response_model=TokenResponse)

@limiter.limit(RATE_LIMITS["login"])  # ✅ Máximo 5 tentativas/minuto
async def login_for_access_token(
        request: Request,  # ✅ Adicionar este parâmetro
        db: GetDBDep,
        form_data: OAuth2PasswordRequestForm = Depends(),
):
    # ✅ Log de tentativa de login (segurança)
    logger.info(f"🔐 Tentativa de login: {form_data.username}")

    user: models.User | None = authenticate_user(email=form_data.username, password=form_data.password, db=db)

    if not user:
        # ✅ Log de falha
        logger.warning(f"⚠️ Login falhou: {form_data.username}")
        raise HTTPException(status_code=401, detail="Incorrect email or password")

    if not user.is_email_verified:
        raise HTTPException(status_code=401, detail="Email not verified")

    if not user.is_active:
        raise HTTPException(status_code=401, detail="Inactive account")

    access_token = create_access_token(data={"sub": user.email})
    refresh_token = create_refresh_token(data={"sub": user.email})

    return {"access_token": access_token, "token_type": "bearer", "refresh_token": refresh_token}




@router.post("/refresh", response_model=TokenResponse)
@limiter.limit("10/minute")  # ✅ Limite para refresh
async def refresh_access_token(
    request: Request,  # ✅ Adicionar
    refresh_token: Annotated[str, Body(..., embed=True)],
    db: GetDBDep
):

    email = verify_refresh_token(refresh_token)
    if not email:
        raise HTTPException(status_code=401, detail="Invalid or expired refresh token")

    # Verifica se o usuário ainda existe e está ativo no banco de dados
    user = db.query(models.User).filter(models.User.email == email, models.User.is_active == True).first()
    if not user:
        raise HTTPException(status_code=401, detail="User not found or inactive")

    # ✅ Cria um NOVO access token
    new_access_token = create_access_token(data={"sub": email})
    # ✅ Cria um NOVO refresh token (Rotação)
    new_refresh_token = create_refresh_token(data={"sub": email})

    # Retorna o novo par de tokens
    return {"access_token": new_access_token, "token_type": "bearer", "refresh_token": new_refresh_token}


@router.post("/change-password")
@limiter.limit(RATE_LIMITS["password_reset"])  # ✅ 3/hora
async def change_password(
    request: Request,  # ✅ Adicionar
    change_password_data: ChangePasswordData,
    db: GetDBDep,
    current_user: GetCurrentUserDep,
):
    user = authenticate_user(email=current_user.email, password=change_password_data.old_password, db=db)
    if not user:
        raise HTTPException(status_code=401)

    user.hashed_password = get_password_hash(change_password_data.new_password)
    db.commit()


# ... (O resto do seu arquivo auth.py permanece igual)
@router.post("/subdomain", response_model=TotemAuthorizationResponse)
def authenticate_by_url(
    db: GetDBDep,
    request_body: AuthenticateByUrlRequest # Recebe o corpo da requisição
):

    totem_auth = db.query(TotemAuthorization).filter(
        TotemAuthorization.store_url == request_body.store_url, # <-- BUSCA PELA store_url
        TotemAuthorization.granted == True # Apenas totens/cardápios autorizados
    ).first()

    if not totem_auth:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Totem authorization not found or not granted for this URL."
        )



    # Atualiza o SID (Session ID) para marcar a sessão ativa
    totem_auth.sid = str(uuid.uuid4())
    totem_auth.updated_at = datetime.utcnow()
    db.add(totem_auth)
    db.commit()
    db.refresh(totem_auth)

    return totem_auth # Retorna o objeto TotemAuthorization completo


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