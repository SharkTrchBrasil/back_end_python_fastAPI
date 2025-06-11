import uuid
from datetime import datetime
from sqlite3 import IntegrityError
from typing import Annotated

from fastapi import APIRouter, Body, HTTPException

from sqlalchemy import select, and_
from starlette import status
from fastapi import Request


from src.api.app.schemas.auth import TotemAuth, TotemAuthorizationResponse, TotemCheckTokenResponse, \
    AuthenticateByUrlRequest, TotemTokenBySubdomainResponse
from src.api.app.schemas.customer import CustomerOut, CustomerCreate, AddressOut, AddressCreate
from src.core import models
from src.core.database import GetDBDep
from src.core.models import TotemAuthorization, Customer, Address

router = APIRouter(tags=["Totem Auth"], prefix="/auth")



@router.post("/subdomain", response_model=TotemAuthorizationResponse)
def authenticate_by_url(
    db: GetDBDep,
    request_body: AuthenticateByUrlRequest # Recebe o corpo da requisição
):

    totem_auth = db.query(TotemAuthorization).filter(
        TotemAuthorization.store_url == request_body.store_url, # <-- BUSCA PELA store_url
        TotemAuthorization.granted == True # Apenas totens/cardápios autorizados
    ).first()

    if not totem_auth:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Totem authorization not found or not granted for this URL."
        )



    # Atualiza o SID (Session ID) para marcar a sessão ativa
    totem_auth.sid = str(uuid.uuid4())
    totem_auth.updated_at = datetime.utcnow()
    db.add(totem_auth)
    db.commit()
    db.refresh(totem_auth)

    return totem_auth # Retorna o objeto TotemAuthorization completo



#
# @router.get("/subdomain", response_model=TotemTokenBySubdomainResponse)
# def get_token_by_host(request: Request, db: GetDBDep):
#     # Extrai o host do cabeçalho
#     host = request.headers.get("host")  # Ex: loja123.zapdelivery.app
#     print(f"HOST HEADER: {host}")
#
#     if not host or '.' not in host:
#         raise HTTPException(status_code=400, detail="Host inválido")
#
#     subdomain = host.split('.')[0]  # Pega o primeiro trecho, ex: 'loja123'
#
#     totem_auth = db.query(models.TotemAuthorization).filter_by(
#         store_url=subdomain,
#         granted=True
#     ).first()
#
#     if not totem_auth:
#         raise HTTPException(status_code=404, detail="Totem não encontrado ou não autorizado")
#
#     return TotemTokenBySubdomainResponse(
#         token=totem_auth.totem_token,
#         store_id=totem_auth.store_id,
#         totem_name=totem_auth.totem_name,
#         store_url=totem_auth.store_url
#     )
#
#
#
#











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





