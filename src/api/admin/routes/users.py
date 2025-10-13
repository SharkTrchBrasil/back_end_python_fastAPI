# src/api/admin/routes/users.py

from fastapi import APIRouter, HTTPException

# Importe seus modelos e o novo utilitário
from src.core import models
from src.core.database import GetDBDep
from src.core.dependencies import GetCurrentUserDep
from src.core.security import generate_verification_code, get_password_hash
from src.core.utils.referral import generate_unique_referral_code
from src.api.schemas.auth.user import UserCreate, UserSchema, UserUpdate
from src.api.admin.utils.email_service import send_verification_email

router = APIRouter(prefix="/users", tags=["Users"])


@router.post("", response_model=UserSchema, status_code=201)
def create_user(user_data: UserCreate, db: GetDBDep):
    # ✅ SUA VALIDAÇÃO DE E-MAIL EXISTENTE
    if db.query(models.User).filter(models.User.email == user_data.email).first():
        raise HTTPException(status_code=409, detail="Este e-mail já está em uso.")

    # ✅ NOVA VALIDAÇÃO DE TELEFONE
    if user_data.phone and db.query(models.User).filter(models.User.phone == user_data.phone).first():
        raise HTTPException(status_code=409, detail="Este telefone já está em uso.")

    # --- LÓGICA DE INDICAÇÃO (REFERRAL) ---
    referrer_id = None
    if user_data.referral_code:
        # Procura o usuário que fez a indicação
        referrer = db.query(models.User).filter(models.User.referral_code == user_data.referral_code).first()
        if referrer:
            referrer_id = referrer.id
    # ----------------------------------------

    hashed_password = get_password_hash(password=user_data.password)
    verification_code = generate_verification_code()

    new_user = models.User(
        email=user_data.email,
        name=user_data.name,
        phone=user_data.phone,
        hashed_password=hashed_password,
        is_email_verified=False,
        is_store_owner=True,  # ✅ Novos usuários são proprietários por padrão
        verification_code=verification_code,

        referral_code=generate_unique_referral_code(db, user_data.name),

        referred_by_user_id=referrer_id
    )

    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    send_verification_email(new_user.email, new_user.verification_code)
    return new_user


@router.get("/me", response_model=UserSchema)
def get_me(current_user: GetCurrentUserDep):
    return current_user


@router.patch("/me", response_model=UserSchema)
def update_me(
        data: UserUpdate,
        db: GetDBDep,
        current_user: GetCurrentUserDep,
):
    # ✅ LÓGICA DE ATUALIZAÇÃO MELHORADA
    # Converte o schema Pydantic em um dicionário, excluindo campos não enviados
    update_data = data.model_dump(exclude_unset=True)

    # Segurança: Se estiver atualizando o CPF, verifica se ele já não está em uso por outro usuário
    if "cpf" in update_data and update_data["cpf"]:
        existing_cpf = db.query(models.User).filter(
            models.User.cpf == update_data["cpf"],
            models.User.id != current_user.id  # Ignora o próprio usuário
        ).first()
        if existing_cpf:
            raise HTTPException(status_code=409, detail="Este CPF já está em uso.")

    # Itera sobre os dados enviados e atualiza o objeto do usuário
    for key, value in update_data.items():
        setattr(current_user, key, value)

    db.add(current_user)
    db.commit()
    db.refresh(current_user)

    return current_user