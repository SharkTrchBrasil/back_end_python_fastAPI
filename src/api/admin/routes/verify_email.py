from fastapi import APIRouter, HTTPException, Depends, Query
from src.core import models
from src.core.database import GetDBDep

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
