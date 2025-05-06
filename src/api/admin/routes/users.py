from fastapi import APIRouter, HTTPException

from src.core import models
from src.core.database import GetDBDep
from src.core.dependencies import GetOptionalUserDep, GetCurrentUserDep
from src.api.admin.schemas.user import UserCreate, User
from src.api.admin.services.auth import get_password_hash
from src.core.email_service import send_verification_email
from src.core.security import generate_verification_token  # novo import

router = APIRouter(prefix="/users", tags=["Users"])

@router.post("", response_model=User, status_code=201)
def create_user(user: UserCreate, db: GetDBDep):
    # Verifica se já existe um usuário com o mesmo e-mail
    existing_user_by_email = db.query(models.User).filter(models.User.email == user.email).first()
    if existing_user_by_email:
        raise HTTPException(status_code=400, detail="User with this email already exists")

    # Verifica se já existe um usuário com o mesmo número de telefone (se fornecido)
    if user.phone_number:
        existing_user_by_phone = db.query(models.User).filter(models.User.phone == user.phone).first()
        if existing_user_by_phone:
            raise HTTPException(status_code=400, detail="User with this phone number already exists")

    # Se o e-mail e (se fornecido) o telefone não existirem, cria o novo usuário
    # Gera o token de verificação
    verification_token = generate_verification_token()

    user_internal_dict = user.model_dump()
    user_internal_dict["hashed_password"] = get_password_hash(password=user_internal_dict["password"])
    user_internal_dict["email_verified"] = False
    user_internal_dict["verification_token"] = verification_token
    del user_internal_dict["password"]

    user_internal = models.User(**user_internal_dict)
    db.add(user_internal)
    db.commit()
    db.refresh(user_internal) # É importante dar um refresh para que o objeto 'user_internal' tenha todos os dados do banco

    # Envia o e-mail de verificação
    send_verification_email(user_internal.email, user_internal.verification_token)

    return user_internal


@router.get("/me", response_model=User)
def get_me(
    current_user: GetCurrentUserDep,
):
    return current_user