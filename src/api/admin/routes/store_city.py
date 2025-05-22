from fastapi import APIRouter, Form, HTTPException, Depends
from sqlalchemy.orm import Session
from src.core.database import GetDBDep
from src.core.dependencies import GetStoreDep
from src.core.models import StoreCity
from src.api.admin.schemas.store_city import StoreCitySchema

router = APIRouter(prefix="/stores/{store_id}/cities", tags=["Cities"])


@router.post("", response_model=StoreCitySchema)
def create_city(
    db: Session = Depends(GetDBDep),
    store = Depends(GetStoreDep),
    name: str = Form(...),
    delivery_fee: float = Form(0.0),

):
    city = StoreCity(
        name=name,
        delivery_fee=delivery_fee,
        store_id=store.id,
    )
    db.add(city)
    db.commit()
    db.refresh(city)
    return city


@router.get("", response_model=list[StoreCitySchema])
def list_cities(
    db: Session = Depends(GetDBDep),
    store = Depends(GetStoreDep),
):
    cities = db.query(StoreCity).filter(StoreCity.store_id == store.id).all()
    return cities


@router.get("/{city_id}", response_model=StoreCitySchema)
def get_city(
    city_id: int,
    db: Session = Depends(GetDBDep),
    store = Depends(GetStoreDep),
):
    city = db.query(StoreCity).filter(StoreCity.id == city_id, StoreCity.store_id == store.id).first()
    if not city:
        raise HTTPException(status_code=404, detail="City not found")
    return city


@router.patch("/{city_id}", response_model=StoreCitySchema)
def update_city(
    city_id: int,
    db: Session = Depends(GetDBDep),
    store = Depends(GetStoreDep),
    name: str | None = Form(None),
    delivery_fee: float | None = Form(None),

):
    city = db.query(StoreCity).filter(StoreCity.id == city_id, StoreCity.store_id == store.id).first()
    if not city:
        raise HTTPException(status_code=404, detail="City not found")

    if name is not None:
        city.name = name
    if delivery_fee is not None:
        city.delivery_fee = delivery_fee


    db.commit()
    db.refresh(city)
    return city


@router.delete("/{city_id}", status_code=204)
def delete_city(
    city_id: int,
    db: Session = Depends(GetDBDep),
    store = Depends(GetStoreDep),
):
    city = db.query(StoreCity).filter(StoreCity.id == city_id, StoreCity.store_id == store.id).first()
    if not city:
        raise HTTPException(status_code=404, detail="City not found")

    db.delete(city)
    db.commit()
