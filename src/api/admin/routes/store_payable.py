from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
from src.core.database import GetDBDep
from src.core.dependencies import GetStoreDep
from src.core.models import StorePayable
from src.api.admin.schemas.store_payable import (
    StorePayableCreate,
    StorePayableUpdate,
    StorePayableOut,
)

router = APIRouter(prefix="/stores/{store_id}/payables", tags=["Payables"])


@router.post("", response_model=StorePayableOut)
def create_payable(
    payload: StorePayableCreate,
    db: GetDBDep,
    store: GetStoreDep,
):
    payable = StorePayable(**payload.dict(), store_id=store.id)
    db.add(payable)
    db.commit()
    db.refresh(payable)
    return payable


@router.get("", response_model=list[StorePayableOut])
def list_payables(
    db: GetDBDep,
    store: GetStoreDep,
):
    return db.query(StorePayable).filter(StorePayable.store_id == store.id).all()


@router.get("/{payable_id}", response_model=StorePayableOut)
def get_payable(
    payable_id: int,
    db: GetDBDep,
    store: GetStoreDep,
):
    payable = db.query(StorePayable).filter(
        StorePayable.id == payable_id,
        StorePayable.store_id == store.id
    ).first()

    if not payable:
        raise HTTPException(status_code=404, detail="Payable not found")

    return payable


@router.patch("/{payable_id}", response_model=StorePayableOut)
def update_payable(
    payable_id: int,
    payload: StorePayableUpdate,
    db: GetDBDep,
    store: GetStoreDep,
):
    payable = db.query(StorePayable).filter(
        StorePayable.id == payable_id,
        StorePayable.store_id == store.id
    ).first()

    if not payable:
        raise HTTPException(status_code=404, detail="Payable not found")

    for key, value in payload.dict(exclude_unset=True).items():
        setattr(payable, key, value)

    db.commit()
    db.refresh(payable)
    return payable


@router.delete("/{payable_id}", status_code=204)
def delete_payable(
    payable_id: int,
    db: GetDBDep,
    store: GetStoreDep,
):
    payable = db.query(StorePayable).filter(
        StorePayable.id == payable_id,
        StorePayable.store_id == store.id
    ).first()

    if not payable:
        raise HTTPException(status_code=404, detail="Payable not found")

    db.delete(payable)
    db.commit()
