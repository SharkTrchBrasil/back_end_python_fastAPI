import uuid
from datetime import datetime
from sqlite3 import IntegrityError
from typing import Annotated

from fastapi import APIRouter, Body, HTTPException

from sqlalchemy import select, and_
from starlette import status

from src.api.app.schemas.auth import TotemAuth, TotemAuthorizationResponse, TotemCheckTokenResponse, \
    AuthenticateByUrlRequest
from src.api.app.schemas.customer import CustomerOut, CustomerCreate, AddressOut, AddressCreate
from src.core import models
from src.core.database import GetDBDep
from src.core.models import TotemAuthorization, Customer, Address

router = APIRouter(tags=["Totem Auth"], prefix="/auth")



@router.post("/authenticate-by-url", response_model=TotemAuthorizationResponse)
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

    # Opcional: Você pode querer verificar o totem_token recebido aqui se for para manter a sessão
    # Ou simplesmente assumir que, se a store_url é válida e granted=True, a sessão é válida
    # Para o seu caso, o foco é na store_url para identificar. O totem_token será retornado.

    # Atualiza o SID (Session ID) para marcar a sessão ativa
    totem_auth.sid = str(uuid.uuid4())
    totem_auth.updated_at = datetime.utcnow()
    db.add(totem_auth)
    db.commit()
    db.refresh(totem_auth)

    return totem_auth # Retorna o objeto TotemAuthorization completo


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




@router.post("/customer/google", response_model=CustomerOut)
async def customer_login_google(customer_in: CustomerCreate, db: GetDBDep):
    result = await db.execute(select(Customer).filter(Customer.email == customer_in.email))
    customer = result.scalars().first()

    if customer:
        customer.name = customer_in.name
        customer.phone = customer_in.phone
        customer.photo = customer_in.photo
        await db.commit()
        await db.refresh(customer)
        return customer

    customer = Customer(
        name=customer_in.name,
        email=customer_in.email,
        phone=customer_in.phone,
        photo=customer_in.photo,
        addresses=[Address(**addr.model_dump()) for addr in customer_in.addresses],
    )
    db.add(customer)
    try:
        await db.commit()
        await db.refresh(customer)
        return customer
    except IntegrityError:
        await db.rollback()
        raise HTTPException(status_code=400, detail="Email já cadastrado")


