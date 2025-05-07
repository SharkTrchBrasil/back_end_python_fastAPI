# routes/verify_code.py
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from src.core.database import GetDBDep # Supondo que esse seja o nome correto do dependente
from src.core.models import User

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
