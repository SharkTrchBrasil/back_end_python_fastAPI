import httpx
from fastapi import APIRouter, HTTPException, Depends, Query
from fastapi.responses import HTMLResponse
from src.core.database import GetDBDep
from src.core import models
from src.core.security import generate_verification_token
from src.api.admin.services.email_service import send_verification_email
from src.api.admin.schemas import user as user_schemas
from pydantic import BaseModel

router = APIRouter(prefix="/verify-email", tags=["Verify Email"])

VERIFY_PAGE_URL = "https://food.zapdelivery.online/verify_email.html"


@router.post("", status_code=200)
async def verify_email(token: str = Query(...), db: GetDBDep = Depends()):
    """Verifica o token de e-mail enviado pelo front-end."""
    user = db.query(models.User).filter(models.User.verification_token == token).first()

    if not user:
        raise HTTPException(status_code=400, detail="Invalid or expired verification token")

    user.is_email_verified = True  # Corrigi o nome do atributo
    user.is_active = True
    user.verification_token = None
    db.commit()

    return {"message": "Email verified successfully"}

@router.post("/resend", status_code=200)
async def resend_verification_email(email: user_schemas.ResendEmail, db: GetDBDep = Depends()):
    """Reenvia o e-mail de verificação para o usuário."""
    user = db.query(models.User).filter(models.User.email == email.email).first()
    if not user:
        raise HTTPException(status_code=404, detail="User with this email not found")
    if user.is_email_verified:  # Corrigi o nome do atributo
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