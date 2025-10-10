from fastapi.security import OAuth2PasswordBearer
from passlib.context import CryptContext
import jwt
from jwt import InvalidTokenError
from datetime import timedelta, datetime, timezone

from src.core import models
from src.core.config import config
import random


def generate_verification_code() -> str:
    """Gera um código de 6 dígitos para verificação por e-mail."""
    return f"{random.randint(100000, 999999)}"


oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/admin/auth/login")

SECRET_KEY = config.SECRET_KEY
REFRESH_SECRET_KEY = config.REFRESH_SECRET_KEY
ALGORITHM = "HS256"

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def get_password_hash(password):
    return pwd_context.hash(password)


def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)


def verify_access_token(token: str):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        email = payload.get("sub")
        return email
    except InvalidTokenError as e:
        return None


# ✅ FUNÇÃO ATUALIZADA
def create_access_token(data: dict, expires_delta: timedelta | None = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        # Usa o valor do arquivo de configuração
        expire = datetime.now(timezone.utc) + timedelta(minutes=config.ACCESS_TOKEN_EXPIRE_MINUTES)

    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


# ✅ FUNÇÃO ATUALIZADA
def create_refresh_token(data: dict, expires_delta: timedelta | None = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        # Usa o valor do arquivo de configuração
        expire = datetime.now(timezone.utc) + timedelta(days=config.REFRESH_TOKEN_EXPIRE_DAYS)

    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, REFRESH_SECRET_KEY, algorithm=ALGORITHM)


def verify_refresh_token(token: str):
    try:
        payload = jwt.decode(token, REFRESH_SECRET_KEY, algorithms=[ALGORITHM])
        return payload.get("sub")
    except InvalidTokenError:
        return None