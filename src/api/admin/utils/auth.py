
from sqlalchemy.orm import Session

from src.core import models
from src.core.security import verify_password



def authenticate_user(email: str, password: str, db: Session) -> models.User | None:
    user: models.User | None = db.query(models.User).filter(models.User.email == email).first()

    if not user:
        return None

    if not verify_password(password, user.hashed_password):
        return None

    return user



