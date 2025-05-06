from fastapi import APIRouter, HTTPException, Depends, Query
from src.core.database import GetDBDep
from src.core import models
from src.core.security import generate_verification_token  # Se você ainda não importou
from src.api.admin.services.email_service import send_verification_email
from src.api.admin.schemas import user as user_schemas  # Importação correta
from pydantic import BaseModel  # Se ainda não importado

router = APIRouter(prefix="/verify-email", tags=["Verify Email"])

@router.post("", status_code=200)
def verify_email(token: str = Query(...), db: GetDBDep = Depends()):
    user = db.query(models.User).filter(models.User.verification_token == token).first()

    if not user:
        raise HTTPException(status_code=400, detail="Invalid or expired verification token")

    user.email_verified = True
    user.is_active = True
    user.verification_token = None
    db.commit()

    return {"message": "Email verified successfully"}

@router.post("/resend", status_code=200)
def resend_verification_email(email: user_schemas.ResendEmail, db: GetDBDep = Depends()):
    user = db.query(models.User).filter(models.User.email == email.email).first()
    if not user:
        raise HTTPException(status_code=404, detail="User with this email not found")
    if user.email_verified:
        raise HTTPException(status_code=400, detail="Email already verified")

    # Gere um novo token de verificação
    verification_token = generate_verification_token()
    user.verification_token = verification_token
    db.commit()

    # Envie o e-mail de verificação novamente
    send_verification_email(user.email, user.verification_token)

    return {"message": "Verification email resent successfully"}

# Defina o schema ResendEmail (se ainda não tiver)
class ResendEmail(BaseModel):
    email: str