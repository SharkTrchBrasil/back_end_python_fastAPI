import asyncio

from fastapi import APIRouter, HTTPException
from sqlalchemy.orm import selectinload
from starlette import status

from src.api.admin.socketio.emitters import admin_emit_store_updated
from src.api.app.socketio.socketio_emitters import emit_store_updated
from src.core.database import GetDBDep
from src.core.dependencies import GetStoreDep
from src.core.models import StoreCity, Store, StoreNeighborhood
from src.api.schemas.store.location.store_city import StoreCitySchema, StoreCityUpsertSchema

router = APIRouter(prefix="/stores/{store_id}", tags=["Cities & Neighborhoods"])


@router.post(
    "/cities-with-neighborhoods",
    response_model=StoreCitySchema,
    summary="Cria ou atualiza uma cidade e seus bairros de uma só vez",
    status_code=status.HTTP_201_CREATED,
)
async def upsert_city_with_neighborhoods(
        store_id: int,
        city_data: StoreCityUpsertSchema,
        db: GetDBDep,
):
    # ✅ CORREÇÃO: Usando `db.get` síncrono
    store = db.get(Store, store_id)
    if not store:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Loja não encontrada")

    city_db = None
    if city_data.id:
        # ✅ CORREÇÃO: Carregando a cidade e seus relacionamentos de forma síncrona
        query = db.query(StoreCity).options(selectinload(StoreCity.neighborhoods)).filter(StoreCity.id == city_data.id)
        city_db = query.first()

        if not city_db or city_db.store_id != store_id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Cidade não encontrada nesta loja")

    if city_db is None:
        city_db = StoreCity(store_id=store_id)
        db.add(city_db)

    city_db.name = city_data.name
    city_db.delivery_fee = city_data.delivery_fee
    city_db.is_active = city_data.is_active

    existing_neighborhoods_map = {n.id: n for n in city_db.neighborhoods}
    incoming_neighborhood_ids = {n.id for n in city_data.neighborhoods if n.id}

    # Deleta bairros que foram removidos no frontend
    for hood_id, hood_db in existing_neighborhoods_map.items():
        if hood_id not in incoming_neighborhood_ids:
            # ✅ CORREÇÃO: Usando `db.delete` síncrono
            db.delete(hood_db)

    updated_neighborhoods_list = []
    for hood_data in city_data.neighborhoods:
        hood_db = existing_neighborhoods_map.get(hood_data.id) if hood_data.id else None
        if hood_db:
            hood_db.name = hood_data.name
            hood_db.delivery_fee = hood_data.delivery_fee
            hood_db.is_active = hood_data.is_active
            updated_neighborhoods_list.append(hood_db)
        else:
            new_hood = StoreNeighborhood(
                name=hood_data.name,
                delivery_fee=hood_data.delivery_fee,
                is_active=hood_data.is_active,
            )
            updated_neighborhoods_list.append(new_hood)

    city_db.neighborhoods = updated_neighborhoods_list

    # ✅ CORREÇÃO: Usando `db.commit` e `db.refresh` síncronos
    db.commit()
    db.refresh(city_db)

    await asyncio.gather(
        emit_store_updated(db, store.id),
        admin_emit_store_updated(db, store.id)
    )

    return city_db


# --- ROTAS DE LEITURA E DELEÇÃO (ajustadas para consistência síncrona) ---

@router.get("/cities", response_model=list[StoreCitySchema],
            summary="Lista todas as cidades e seus bairros para uma loja")
def list_cities(
        store: GetStoreDep,
):
    return store.cities


@router.get("/cities/{city_id}", response_model=StoreCitySchema, summary="Obtém uma cidade específica com seus bairros")
def get_city(
        city_id: int,
        store: GetStoreDep,
        db: GetDBDep,
):
    # ✅ CORREÇÃO: Usando `db.get` síncrono
    city = db.get(StoreCity, city_id)
    if not city or city.store_id != store.id:
        raise HTTPException(status_code=404, detail="City not found")
    return city


@router.delete("/cities/{city_id}", status_code=status.HTTP_204_NO_CONTENT,
               summary="Deleta uma cidade e todos os seus bairros")
async def delete_city(
        city_id: int,
        store: GetStoreDep,
        db: GetDBDep,
):
    # ✅ CORREÇÃO: Usando `db.get` síncrono
    city = db.get(StoreCity, city_id)
    if not city or city.store_id != store.id:
        raise HTTPException(status_code=404, detail="City not found")

    # ✅ CORREÇÃO: Usando `db.delete` e `db.commit` síncronos
    db.delete(city)
    db.commit()

    await asyncio.gather(
        emit_store_updated(db, store.id),
        admin_emit_store_updated(db, store.id)
    )
    return None