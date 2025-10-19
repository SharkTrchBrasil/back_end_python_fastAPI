from sqlalchemy.orm import Session
from passlib.context import CryptContext
from datetime import datetime, timedelta
from jose import JWTError, jwt
from typing import Optional
import os

from src.core import models

# ✅ Configuração do contexto de hash de senha
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# ✅ Configurações JWT
SECRET_KEY = os.getenv("SECRET_KEY", "your-secret-key-here")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30


# ✅ CORRIGIDO: Agora recebe Session, não generator
def authenticate_user(db: Session, email: str, password: str) -> models.User | None:
    """
    Autentica um usuário verificando email e senha.

    Args:
        db: Sessão do banco de dados (Session, não generator!)
        email: Email do usuário
        password: Senha em texto plano

    Returns:
        User object se autenticado, None caso contrário
    """
    # ✅ Agora db.query funciona porque é uma Session
    user: models.User | None = db.query(models.User).filter(
        models.User.email == email
    ).first()

    if not user:
        return None

    # Verifica a senha
    if not verify_password(password, user.hashed_password):
        return None

    return user


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verifica se a senha em texto plano corresponde ao hash."""
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    """Cria um hash da senha."""
    return pwd_context.hash(password)


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """
    Cria um token JWT de acesso.

    Args:
        data: Dados a serem codificados no token (ex: {"sub": user_id})
        expires_delta: Tempo de expiração customizado

    Returns:
        Token JWT codificado
    """
    to_encode = data.copy()

    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)

    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

    return encoded_jwt


def decode_access_token(token: str) -> dict | None:
    """
    Decodifica e valida um token JWT.

    Args:
        token: Token JWT para decodificar

    Returns:
        Payload do token se válido, None caso contrário
    """
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except JWTError:
        return None


def get_current_user(db: Session, token: str) -> models.User | None:
    """
    Obtém o usuário atual a partir do token JWT.

    Args:
        db: Sessão do banco de dados
        token: Token JWT

    Returns:
        User object se token válido, None caso contrário
    """
    payload = decode_access_token(token)

    if payload is None:
        return None

    user_id: str | None = payload.get("sub")

    if user_id is None:
        return None

    user = db.query(models.User).filter(models.User.id == int(user_id)).first()

    return user