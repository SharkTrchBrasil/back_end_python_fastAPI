from fastapi import APIRouter, HTTPException
from sqlalchemy import and_
from sqlalchemy.future import select
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



@router.post("/{customer_id}/addresses", response_model=AddressOut)
async def add_address(customer_id: int, address_in: AddressCreate, db: GetDBDep):
    result = await db.execute(select(Customer).where(Customer.id == customer_id))
    customer = result.scalars().first()

    if not customer:
        raise HTTPException(status_code=404, detail="Cliente não encontrado")

    address = Address(**address_in.model_dump(), customer_id=customer_id)
    db.add(address)
    await db.commit()
    await db.refresh(address)
    return address


@router.delete("/{customer_id}/addresses/{address_id}", status_code=204)
async def delete_address(customer_id: int, address_id: int, db: GetDBDep):
    result = await db.execute(
        select(Address).where(and_(Address.id == address_id, Address.customer_id == customer_id))
    )
    address = result.scalars().first()

    if not address:
        raise HTTPException(status_code=404, detail="Endereço não encontrado")

    await db.delete(address)
    await db.commit()
    return None  # Retorno explícito para 204 No Content
