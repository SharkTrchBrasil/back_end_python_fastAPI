from fastapi import APIRouter, HTTPException

from src.core import models
from src.core.database import GetDBDep
from src.core.dependencies import GetOptionalUserDep, GetCurrentUserDep
from src.api.admin.schemas.user import UserCreate, User
from src.api.admin.services.auth import get_password_hash

router = APIRouter(prefix="/users", tags=["Users"])

@router.post("", response_model=User, status_code=201)
def create_user(user: UserCreate, db: GetDBDep):
    existing_user = db.query(models.User).filter(models.User.email == user.email).first()
    if existing_user:
        raise HTTPException(status_code=400, detail="User already exists")

    user_internal_dict = user.model_dump()
    user_internal_dict["hashed_password"] = get_password_hash(password=user_internal_dict["password"])
    del user_internal_dict["password"]

    user_internal = models.User(**user_internal_dict)
    db.add(user_internal)
    db.commit()
    return user_internal


@router.get("/me", response_model=User)
def get_me(
    current_user: GetCurrentUserDep,
):
    return current_user