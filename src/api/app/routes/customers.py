from fastapi import APIRouter, HTTPException
from sqlalchemy.future import select
from sqlalchemy.exc import IntegrityError

from src.api.app.schemas.customer import CustomerCreate, CustomerOut, Address
from src.core.database import GetDBDep
from src.core.models import Customer

router = APIRouter()

@router.post("/customers/login-google", response_model=CustomerOut)
async def login_google(customer_in: CustomerCreate, db: GetDBDep):
    result = await db.execute(select(Customer).filter(Customer.email == customer_in.email))
    customer = result.scalars().first()

    if customer:
        customer.name = customer_in.name
        customer.phone = customer_in.phone
        await db.commit()
        await db.refresh(customer)
        return customer

    customer = Customer(
        name=customer_in.name,
        email=customer_in.email,
        phone=customer_in.phone,
        addresses=[Address(**addr.model_dump()) for addr in customer_in.addresses]
    )
    db.add(customer)
    try:
        await db.commit()
        await db.refresh(customer)
        return customer
    except IntegrityError:
        await db.rollback()
        raise HTTPException(status_code=400, detail="Email already registered")
