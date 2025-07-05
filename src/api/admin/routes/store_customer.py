from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List

from src.api.admin.schemas.customer import StoreCustomerOut
from src.core.database import GetDBDep
from src.core.models import StoreCustomer, Customer


router = APIRouter(prefix="/stores/{store_id}/customers", tags=["Clientes da Loja"])

@router.get("", response_model=List[StoreCustomerOut])
def list_store_customers(store_id: int, db: GetDBDep):
    """
    Lista os clientes vinculados à loja, com dados agregados (pedidos, gasto, última compra).
    """
    results = db.query(
        StoreCustomer,
        Customer
    ).join(Customer, StoreCustomer.customer_id == Customer.id).filter(
        StoreCustomer.store_id == store_id
    ).order_by(StoreCustomer.last_order_at.desc()).all()

    output = []
    for store_customer, customer in results:
        output.append(StoreCustomerOut(
            customer_id=customer.id,
            name=customer.name,
            phone=customer.phone,
            email=getattr(customer, "email", None),
            total_orders=store_customer.total_orders,
            total_spent=store_customer.total_spent,
            last_order_at=store_customer.last_order_at,
        ))
    return output



