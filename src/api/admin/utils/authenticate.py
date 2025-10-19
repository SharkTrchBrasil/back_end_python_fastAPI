from sqlalchemy.orm import Session
from src.core import models
from src.core.security.security import verify_password


def authenticate_user(db, email: str, password: str) -> models.User | None:
    """
    Autentica um usuário verificando email e senha.

    Args:
        db: Sessão do banco de dados (PRIMEIRO parâmetro!)
        email: Email do usuário
        password: Senha em texto plano

    Returns:
        User object se autenticado, None caso contrário
    """
    user: models.User | None = db.query(models.User).filter(
        models.User.email == email
    ).first()

    if not user:
        return None

    if not verify_password(password, user.hashed_password):
        return None

    return user