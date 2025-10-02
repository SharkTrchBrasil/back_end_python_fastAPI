import asyncio

from fastapi import APIRouter, HTTPException
from starlette import status

from src.api.admin.socketio.emitters import admin_emit_store_updated
from src.api.app.socketio.socketio_emitters import emit_store_updated
from src.core.database import GetDBDep
from src.core.dependencies import GetStoreDep
from src.core.models import StoreCity, Store, StoreNeighborhood
from src.api.schemas.store.location.store_city import StoreCitySchema, StoreCityUpsertSchema

# O prefixo agora é só até a loja, a rota específica define o resto.
router = APIRouter(prefix="/stores/{store_id}", tags=["Cities & Neighborhoods"])


@router.post(
    "/cities-with-neighborhoods",  # Rota mais limpa: /stores/{store_id}/cities-with-neighborhoods
    response_model=StoreCitySchema,
    summary="Cria ou atualiza uma cidade e seus bairros de uma só vez",
    status_code=status.HTTP_201_CREATED,  # Usando 201 para criação/update bem sucedido
)
async def upsert_city_with_neighborhoods(
        store_id: int,
        city_data: StoreCityUpsertSchema,
        db: GetDBDep,
        # current_user: User = Depends(get_current_active_user), # Lembre-se de proteger sua rota!
):
    # 1. Busca a loja e a cidade (se for uma atualização)
    store = await db.get(Store, store_id)
    if not store:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Loja não encontrada")

    city_db = None
    if city_data.id:
        # Carrega a cidade e seus bairros de uma vez para otimizar
        city_db = await db.get(StoreCity, city_data.id)
        if not city_db or city_db.store_id != store_id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Cidade não encontrada nesta loja")

    if city_db is None:
        # Cria uma nova instância de cidade se não for uma atualização
        city_db = StoreCity(store_id=store_id)
        db.add(city_db)

    # 2. Atualiza os dados da cidade
    city_db.name = city_data.name
    city_db.delivery_fee = city_data.delivery_fee
    city_db.is_active = city_data.is_active

    # 3. Sincroniza os bairros
    existing_neighborhoods_map = {n.id: n for n in city_db.neighborhoods}
    incoming_neighborhood_ids = {n.id for n in city_data.neighborhoods if n.id}

    # Deleta bairros que foram removidos no frontend
    for hood_id, hood_db in existing_neighborhoods_map.items():
        if hood_id not in incoming_neighborhood_ids:
            await db.delete(hood_db)

    # Atualiza bairros existentes e adiciona novos
    updated_neighborhoods_list = []
    for hood_data in city_data.neighborhoods:
        hood_db = existing_neighborhoods_map.get(hood_data.id) if hood_data.id else None
        if hood_db:  # Atualiza bairro existente
            hood_db.name = hood_data.name
            hood_db.delivery_fee = hood_data.delivery_fee
            hood_db.is_active = hood_data.is_active
            updated_neighborhoods_list.append(hood_db)
        else:  # Adiciona novo bairro
            new_hood = StoreNeighborhood(
                name=hood_data.name,
                delivery_fee=hood_data.delivery_fee,
                is_active=hood_data.is_active,
            )
            updated_neighborhoods_list.append(new_hood)

    city_db.neighborhoods = updated_neighborhoods_list

    # 4. Salva tudo no banco e emite o socket
    await db.commit()
    await db.refresh(city_db)

    # ✅ CORREÇÃO: Emite o evento de atualização para o frontend
    await asyncio.gather(
        emit_store_updated(db, store.id),
        admin_emit_store_updated(db, store.id)
    )

    return city_db


@router.get("/cities", response_model=list[StoreCitySchema],
            summary="Lista todas as cidades e seus bairros para uma loja")
async def list_cities(
        store: GetStoreDep,
):
    # Acessa as cidades diretamente pelo relacionamento da loja, que já foi configurado com cascade
    return store.cities


@router.get("/cities/{city_id}", response_model=StoreCitySchema, summary="Obtém uma cidade específica com seus bairros")
async def get_city(
        city_id: int,
        store: GetStoreDep,
        db: GetDBDep,
):
    city = await db.get(StoreCity, city_id)
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
    city = await db.get(StoreCity, city_id)
    if not city or city.store_id != store.id:
        raise HTTPException(status_code=404, detail="City not found")

    await db.delete(city)
    await db.commit()

    # Emite o evento de atualização
    await asyncio.gather(
        emit_store_updated(db, store.id),
        admin_emit_store_updated(db, store.id)
    )
    return None

#
# --- ROTAS ANTIGAS REMOVIDAS ---
# As rotas que usavam `Form(...)` foram removidas pois o novo fluxo é baseado em JSON.
# A rota `upsert_city_with_neighborhoods` substitui a necessidade de `create_city` e `update_city` separados.
# A rota de bairros separada também não é mais necessária.
#