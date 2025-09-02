import asyncio
from fastapi import APIRouter, Form, HTTPException

from src.api.admin.socketio.emitters import admin_emit_store_updated
from src.api.app.socketio.socketio_emitters import emit_store_updated
from src.core.models import Store

from src.core.database import GetDBDep
from src.core.models import StoreNeighborhood, StoreCity
from src.api.schemas.store.location.store_neighborhood import StoreNeighborhoodSchema

router = APIRouter(prefix="/cities/{city_id}/neighborhoods", tags=["Neighborhoods"])


def get_store_from_city(db, city_id: int) -> Store:
    city = db.query(StoreCity).filter(StoreCity.id == city_id).first()
    if not city:
        raise HTTPException(status_code=404, detail="City not found")

    store = db.query(Store).filter(Store.id == city.store_id).first()
    if not store:
        raise HTTPException(status_code=404, detail="Store not found")

    return store

@router.post("", response_model=StoreNeighborhoodSchema)
async def create_neighborhood(
    city_id: int,
    db: GetDBDep,
    name: str = Form(...),
    delivery_fee: int = Form(0),
    free_delivery: bool = Form(False),
    is_active: bool = Form(True),
):
    neighborhood = StoreNeighborhood(
        name=name,
        city_id=city_id,
        delivery_fee=delivery_fee,
        free_delivery=free_delivery,
        is_active=is_active,
    )
    db.add(neighborhood)
    db.commit()
    db.refresh(neighborhood)

    store = get_store_from_city(db, city_id)
    await asyncio.create_task(emit_store_updated(db, store.id))
    await admin_emit_store_updated(db, store.id)
    return neighborhood


@router.get("", response_model=list[StoreNeighborhoodSchema])
def list_neighborhoods(city_id: int, db: GetDBDep):
    neighborhoods = db.query(StoreNeighborhood).filter(StoreNeighborhood.city_id == city_id).all()
    return neighborhoods


@router.get("/{neighborhood_id}", response_model=StoreNeighborhoodSchema)
def get_neighborhood(city_id: int, neighborhood_id: int, db: GetDBDep):
    neighborhood = (
        db.query(StoreNeighborhood)
        .join(StoreCity, StoreNeighborhood.city_id == StoreCity.id)
        .filter(
            StoreNeighborhood.id == neighborhood_id,
            StoreNeighborhood.city_id == city_id,
        )
        .first()
    )
    if not neighborhood:
        raise HTTPException(status_code=404, detail="Neighborhood not found")
    return neighborhood


@router.patch("/{neighborhood_id}", response_model=StoreNeighborhoodSchema)
async def update_neighborhood(
    city_id: int,
    neighborhood_id: int,
    db: GetDBDep,
    name: str | None = Form(None),
    delivery_fee: int | None = Form(None),
    free_delivery: bool | None = Form(None),
    is_active: bool | None = Form(None),
):
    neighborhood = (
        db.query(StoreNeighborhood)
        .join(StoreCity, StoreNeighborhood.city_id == StoreCity.id)
        .filter(
            StoreNeighborhood.id == neighborhood_id,
            StoreNeighborhood.city_id == city_id,
        )
        .first()
    )
    if not neighborhood:
        raise HTTPException(status_code=404, detail="Neighborhood not found")

    if name is not None:
        neighborhood.name = name
    if delivery_fee is not None:
        neighborhood.delivery_fee = delivery_fee
    if free_delivery is not None:
        neighborhood.free_delivery = free_delivery
    if is_active is not None:
        neighborhood.is_active = is_active

    db.commit()
    db.refresh(neighborhood)
    store = get_store_from_city(db, city_id)
    await asyncio.create_task(emit_store_updated(db, store.id))
    await admin_emit_store_updated(db, store.id)
    return neighborhood


@router.delete("/{neighborhood_id}", status_code=204)
async def delete_neighborhood(city_id: int, neighborhood_id: int, db: GetDBDep):
    neighborhood = (
        db.query(StoreNeighborhood)
        .join(StoreCity, StoreNeighborhood.city_id == StoreCity.id)
        .filter(
            StoreNeighborhood.id == neighborhood_id,
            StoreNeighborhood.city_id == city_id,
        )
        .first()
    )
    if not neighborhood:
        raise HTTPException(status_code=404, detail="Neighborhood not found")

    db.delete(neighborhood)
    db.commit()
    db.refresh(neighborhood)

    store = get_store_from_city(db, city_id)
    await asyncio.create_task(emit_store_updated(db, store.id))
    await admin_emit_store_updated(db, store.id)