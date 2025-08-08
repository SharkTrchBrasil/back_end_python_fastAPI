# routes/verify_code.py
from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import select

from src.api.schemas.resend_code import ResendCodeRequest
from src.api.admin.utils.email_service import send_verification_email
from src.core.database import GetDBDep # Supondo que esse seja o nome correto do dependente
from src.core.models import User
from src.core.security import generate_verification_code

router = APIRouter(tags=["Code"], prefix="/verify-code")



@router.post("")  # Mantemos o método GET
async def verify_code(
    db: GetDBDep,
    email: str = Query(...),  # Parâmetros continuam vindo pela URL como Query
    code: str = Query(...),
):
    stmt = select(User).where(User.email == email)
    result = db.execute(stmt)
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(status_code=404, detail="Usuário não encontrado.")
    if user.is_email_verified:
        raise HTTPException(status_code=400, detail="Código já validado.")
    if user.verification_code != code:
        raise HTTPException(status_code=400, detail="Código incorreto.")

    user.is_email_verified = True
    user.is_active = True
    user.verification_code = None
    db.commit()

    return {"message": "Código validado com sucesso."}


@router.post("/resend")
async def resend_verification_code(
    db: GetDBDep,
  body: ResendCodeRequest,
):
    email = body.email
    if not email:
        raise HTTPException(status_code=400, detail="Email é obrigatório.")

    stmt = select(User).where(User.email == email)
    result = db.execute(stmt)
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(status_code=404, detail="Usuário não encontrado.")

    if user.is_email_verified:
        raise HTTPException(status_code=400, detail="Email já verificado.")

    # Gerar novo código de verificação
    user.verification_code = generate_verification_code()
    db.commit()

    # Enviar e-mail com o novo código
    send_verification_email(user.email, user.verification_code)

    return {"message": "Código de verificação reenviado com sucesso."}



