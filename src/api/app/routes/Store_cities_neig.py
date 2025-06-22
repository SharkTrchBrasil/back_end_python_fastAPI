from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from typing import List

from src.api.shared_schemas.store_neighborhood import StoreNeighborhoodOut
from src.core.database import GetDBDep
from src.core.models import Store, StoreCity, StoreNeighborhood
from src.api.shared_schemas.store_city import StoreCityOut  # Certifique-se que esse schema exista

router = APIRouter(tags=["Cidades e Bairros"], prefix="/stores")

@router.get("/{store_id}/cities", response_model=List[StoreCityOut])
def get_store_cities(store_id: int, db: GetDBDep):
    store = db.scalar(select(Store).where(Store.id == store_id))
    if not store:
        raise HTTPException(status_code=404, detail="Loja não encontrada")

    return store.cities  # ou: db.scalars(select(StoreCity).where(StoreCity.store_id == store_id)).all()




@router.get("/cities/{city_id}/neighborhoods", response_model=List[StoreNeighborhoodOut])
def get_neighborhoods_by_city(city_id: int, db: GetDBDep):
    neighborhoods = db.scalars(
        select(StoreNeighborhood).where(StoreNeighborhood.city_id == city_id)
    ).all()
    return neighborhoods
