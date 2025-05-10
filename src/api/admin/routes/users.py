from fastapi import APIRouter, HTTPException

from src.core import models
from src.core.database import GetDBDep
from src.core.dependencies import GetCurrentUserDep
from src.api.admin.schemas.user import UserCreate, User, UserUpdate
from src.api.admin.services.auth import get_password_hash
from src.api.admin.services.email_service import send_verification_email
from src.core.security import generate_verification_code  # novo import

router = APIRouter(prefix="/users", tags=["Users"])

@router.post("", response_model=User, status_code=201)
def create_user(user: UserCreate, db: GetDBDep):
    # Verifica se já existe um usuário com o mesmo e-mail
    existing_user_by_email = db.query(models.User).filter(models.User.email == user.email).first()
    if existing_user_by_email:
        raise HTTPException(status_code=400, detail="User with this email already exists")


    verification_code = generate_verification_code()

    user_internal_dict = user.model_dump()
    user_internal_dict["hashed_password"] = get_password_hash(password=user_internal_dict["password"])
    user_internal_dict["is_email_verified"] = False
    user_internal_dict["verification_code"] = verification_code
    del user_internal_dict["password"]

    user_internal = models.User(**user_internal_dict)
    db.add(user_internal)
    db.commit()
    db.refresh(user_internal) # É importante dar um refresh para que o objeto 'user_internal' tenha todos os dados do banco

    # Envia o e-mail de verificação
    send_verification_email(user_internal.email, user_internal.verification_code)

    return user_internal


@router.get("/me", response_model=User)
def get_me(
    current_user: GetCurrentUserDep,
):
    return current_user



@router.patch("/me", response_model=User)
def update_me(
    data: UserUpdate,
    db: GetDBDep,
    current_user: GetCurrentUserDep,
):
    user = db.query(models.User).filter(models.User.id == current_user.id).first()

    if not user:
        raise HTTPException(status_code=404, detail="Usuário não encontrado")

    if data.name is not None:
        user.name = data.name


    db.commit()
    db.refresh(user)

    return user