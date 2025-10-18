# src/core/security.py

import uuid
from datetime import timedelta, datetime, timezone
from typing import Optional

import jwt
from jwt import InvalidTokenError
from passlib.context import CryptContext
from fastapi.security import OAuth2PasswordBearer

from src.core.config import config  # ✅ Importa o objeto config
from src.core.security.token_blacklist import TokenBlacklist

# ═══════════════════════════════════════════════════════════
# CONSTANTES DE SEGURANÇA
# ═══════════════════════════════════════════════════════════

# ✅ PEGA AS CHAVES DO CONFIG
SECRET_KEY = config.SECRET_KEY
REFRESH_SECRET_KEY = config.REFRESH_SECRET_KEY
ALGORITHM = "HS256"  # ✅ Algoritmo padrão JWT

# ✅ OAuth2 scheme para FastAPI
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/admin/auth/login")

# ✅ Context para hash de senhas (bcrypt)
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


# ═══════════════════════════════════════════════════════════
# FUNÇÕES DE HASHING DE SENHA
# ═══════════════════════════════════════════════════════════

def get_password_hash(password: str) -> str:
    """Gera hash bcrypt da senha"""
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verifica se senha corresponde ao hash"""
    return pwd_context.verify(plain_password, hashed_password)


# ═══════════════════════════════════════════════════════════
# FUNÇÕES DE CRIAÇÃO DE TOKENS
# ═══════════════════════════════════════════════════════════

def create_access_token(
        data: dict,
        expires_delta: timedelta | None = None,
        jti: Optional[str] = None
) -> str:
    """
    Cria um access token JWT com JTI único.

    Args:
        data: Dados a serem incluídos no token (ex: {"sub": email})
        expires_delta: Tempo customizado de expiração (opcional)
        jti: JWT ID único (gerado automaticamente se não fornecido)

    Returns:
        Token JWT codificado como string
    """
    to_encode = data.copy()

    # Define expiração
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(
            minutes=config.ACCESS_TOKEN_EXPIRE_MINUTES
        )

    # ✅ Gera JTI único se não fornecido
    if jti is None:
        jti = str(uuid.uuid4())

    # Adiciona claims padrão
    to_encode.update({
        "exp": expire,
        "jti": jti,  # ✅ ID único do token
        "iat": datetime.now(timezone.utc),  # ✅ Issued at
        "type": "access"  # ✅ Tipo do token
    })

    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def create_refresh_token(
        data: dict,
        expires_delta: timedelta | None = None,
        jti: Optional[str] = None
) -> str:
    """
    Cria um refresh token JWT com JTI único.

    Args:
        data: Dados a serem incluídos no token (ex: {"sub": email})
        expires_delta: Tempo customizado de expiração (opcional)
        jti: JWT ID único (gerado automaticamente se não fornecido)

    Returns:
        Refresh token JWT codificado como string
    """
    to_encode = data.copy()

    # Define expiração
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(
            days=config.REFRESH_TOKEN_EXPIRE_DAYS
        )

    # ✅ Gera JTI único se não fornecido
    if jti is None:
        jti = str(uuid.uuid4())

    # Adiciona claims padrão
    to_encode.update({
        "exp": expire,
        "jti": jti,  # ✅ ID único do token
        "iat": datetime.now(timezone.utc),
        "type": "refresh"  # ✅ Tipo do token
    })

    return jwt.encode(to_encode, REFRESH_SECRET_KEY, algorithm=ALGORITHM)


# ═══════════════════════════════════════════════════════════
# FUNÇÕES DE VERIFICAÇÃO DE TOKENS
# ═══════════════════════════════════════════════════════════

def verify_access_token(token: str) -> Optional[dict]:
    """
    ✅ VERSÃO SEGURA: Valida token E verifica blacklist

    Args:
        token: Token JWT a ser validado

    Returns:
        dict com payload do token se válido, None se inválido/revogado
    """
    try:
        # 1. Decodifica e valida assinatura + expiração
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])

        # 2. ✅ VERIFICA BLACKLIST
        jti = payload.get("jti")
        if jti and TokenBlacklist.is_blacklisted(jti):
            print(f"⚠️ Token revogado detectado: {jti[:8]}...")
            return None

        # 3. Valida tipo do token
        if payload.get("type") != "access":
            print(f"⚠️ Tipo de token inválido: {payload.get('type')}")
            return None

        return payload

    except InvalidTokenError as e:
        print(f"❌ Token inválido: {e}")
        return None


def verify_refresh_token(token: str) -> Optional[dict]:
    """
    ✅ VERSÃO SEGURA: Valida refresh token E verifica blacklist

    Args:
        token: Refresh token JWT a ser validado

    Returns:
        dict com payload do token se válido, None se inválido/revogado
    """
    try:
        # 1. Decodifica e valida
        payload = jwt.decode(token, REFRESH_SECRET_KEY, algorithms=[ALGORITHM])

        # 2. ✅ VERIFICA BLACKLIST
        jti = payload.get("jti")
        if jti and TokenBlacklist.is_blacklisted(jti):
            print(f"⚠️ Refresh token revogado detectado: {jti[:8]}...")
            return None

        # 3. Valida tipo
        if payload.get("type") != "refresh":
            print(f"⚠️ Tipo de refresh token inválido")
            return None

        return payload

    except InvalidTokenError as e:
        print(f"❌ Refresh token inválido: {e}")
        return None


# ═══════════════════════════════════════════════════════════
# FUNÇÃO DE GERAÇÃO DE CÓDIGO DE VERIFICAÇÃO
# ═══════════════════════════════════════════════════════════

def generate_verification_code() -> str:
    """Gera um código de 6 dígitos para verificação por e-mail."""
    import random
    return f"{random.randint(100000, 999999)}"