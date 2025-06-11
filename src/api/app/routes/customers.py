from fastapi import APIRouter, HTTPException
from sqlalchemy import and_, select
from sqlalchemy.exc import IntegrityError

from src.api.app.schemas.customer import (
    CustomerCreate,
    CustomerOut,
    AddressCreate,
    AddressOut,
)
from src.core.database import GetDBDep
from src.core.models import Customer, Address

router = APIRouter(tags=["Customers Info"], prefix="/customer")


@router.post("/google", response_model=CustomerOut)
def customer_login_google(customer_in: CustomerCreate, db: GetDBDep):
    result = db.execute(select(Customer).filter(Customer.email == customer_in.email))
    customer = result.scalars().first()

    if customer:
        customer.name = customer_in.name
        customer.phone = customer_in.phone
        customer.photo = customer_in.photo
        db.commit()
        db.refresh(customer)
        return customer

    customer = Customer(
        name=customer_in.name,
        email=customer_in.email,
        phone=customer_in.phone,
        photo=customer_in.photo,
        customers_addresses=[Address(**addr.model_dump()) for addr in customer_in.addresses],
    )
    db.add(customer)
    try:
        db.commit()
        db.refresh(customer)
        return customer
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=400, detail="Email já cadastrado")


@router.post("/{customer_id}/addresses", response_model=AddressOut)
def add_address(customer_id: int, address_in: AddressCreate, db: GetDBDep):
    result = db.execute(select(Customer).where(Customer.id == customer_id))
    customer = result.scalars().first()

    if not customer:
        raise HTTPException(status_code=404, detail="Cliente não encontrado")

    address = Address(**address_in.model_dump(), customer_id=customer_id)
    db.add(address)
    db.commit()
    db.refresh(address)
    return address


@router.delete("/{customer_id}/addresses/{address_id}", status_code=204)
def delete_address(customer_id: int, address_id: int, db: GetDBDep):
    result = db.execute(
        select(Address).where(
            and_(
                Address.id == address_id,
                Address.customer_id == customer_id,
            )
        )
    )
    address = result.scalars().first()

    if not address:
        raise HTTPException(status_code=404, detail="Endereço não encontrado")

    db.delete(address)
    db.commit()
    return None
