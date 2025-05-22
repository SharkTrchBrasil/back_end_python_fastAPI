import uuid
from typing import Annotated

from fastapi import APIRouter, Body, HTTPException

from src.api.app.schemas.auth import TotemAuth, TotemCheckTokenResponse
from src.core import models
from src.core.database import GetDBDep

router = APIRouter(tags=["Totem Auth"], prefix="/auth")

@router.post("/start", response_model=TotemCheckTokenResponse)
def start_auth(
    db: GetDBDep,
    totem_auth: TotemAuth,
):
    auth = db.query(models.TotemAuthorization).filter_by(
        totem_token=totem_auth.totem_token
    ).first()

    if auth:
        auth.totem_name = totem_auth.totem_name
    else:
        auth = models.TotemAuthorization(**totem_auth.model_dump(), public_key=uuid.uuid4())
        db.add(auth)

    db.commit()
    return auth

@router.post("/check-token", response_model=TotemCheckTokenResponse)
def check_token(
    db: GetDBDep,
    totem_token: Annotated[str, Body(..., embed=True)]
):
    auth = db.query(models.TotemAuthorization).filter_by(
        totem_token=totem_token
    ).first()

    if not auth:
        raise HTTPException(status_code=404)

    return auth
