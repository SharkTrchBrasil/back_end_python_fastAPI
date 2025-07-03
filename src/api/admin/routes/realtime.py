
from urllib.parse import parse_qs


from sqlalchemy.orm import joinedload

from src.api.admin.schemas.orders import Order
from src.api.app.schemas.store_details import StoreDetails


from src.api.app.services.rating import (
    get_store_ratings_summary,
    get_product_ratings_summary,
)

from src.api.shared_schemas.product import ProductOut
from src.api.shared_schemas.rating import RatingsSummaryOut
from src.api.shared_schemas.store_theme import StoreThemeOut

from src.core import models
from src.core.database import get_db_manager

from src.core.helpers.authorize_totem import authorize_totem

from src.socketio_instance import sio



async def refresh_product_list(db, store_id: int, sid: str | None = None):
    products_l = db.query(models.Product).options(
        joinedload(models.Product.variant_links)
        .joinedload(models.ProductVariantProduct.variant)
        .joinedload(models.Variant.options)
    ).filter_by(store_id=store_id, available=True).all()

    # Pega avaliações dos produtos
    product_ratings = {
        product.id: get_product_ratings_summary(db, product_id=product.id)
        for product in products_l
    }

    # Junta dados do produto + avaliações
    payload = [
        {
            **ProductOut.from_orm_obj(product).model_dump(exclude_unset=True),
            "rating": product_ratings.get(product.id),
        }
        for product in products_l
    ]

    target = sid if sid else f"store_{store_id}"
    await sio.emit("products_updated", payload, to=target)


# Evento de conexão do Socket.IO
@sio.event
async def connect(sid, environ):
    query = parse_qs(environ.get("QUERY_STRING", ""))
    token = query.get("totem_token", [None])[0]
    print(f"🔥 ADMIN socket connect: SID={sid}, Query={environ.get('QUERY_STRING')}")
    if not token:
        raise ConnectionRefusedError("Missing token")

    with get_db_manager() as db:
        totem = await authorize_totem(db, token)
        if not totem:
            raise ConnectionRefusedError("Invalid or unauthorized token")

        # Atualiza o SID do totem
        totem.sid = sid
        db.commit()

        room_name = f"store_{totem.store_id}"
        await sio.enter_room(sid, room_name)

        # Carrega dados completos da loja com seus relacionamentos
        # Loja -> delivery_config
        # Loja -> Cidades -> Bairros
        store = db.query(models.Store).options(
            joinedload(models.Store.payment_methods),
            joinedload(models.Store.delivery_config),  # Carrega a configuração de entrega (sem cidades/bairros aqui)
            joinedload(models.Store.hours),
            # Carrega as cidades da loja e, para cada cidade, seus bairros
            joinedload(models.Store.cities).joinedload(models.StoreCity.neighborhoods),
        ).filter_by(id=totem.store_id).first()

        if store:
            # Envia dados da loja com avaliações
            try:
                # Converte o objeto SQLAlchemy 'store' para o Pydantic 'StoreDetails'
                store_schema = StoreDetails.model_validate(store)
            except Exception as e:
                print(f"Erro ao validar Store com Pydantic StoreDetails para loja {store.id}: {e}")
                # Isso pode indicar que StoreDetails ou seus aninhados (StoreCity Pydantic, StoreNeighborhood Pydantic)
                # não estão configurados corretamente com model_config = {"from_attributes": True, "arbitrary_types_allowed": True}
                raise ConnectionRefusedError(f"Erro interno do servidor: Dados da loja malformados: {e}")

            store_schema.ratingsSummary = RatingsSummaryOut(
                **get_store_ratings_summary(db, store_id=store.id)
            )
            # Converte o modelo Pydantic para um dicionário serializável para JSON
            store_payload = store_schema.model_dump()
            await sio.emit("store_updated", store_payload, to=sid)

            # Envia tema
            theme = db.query(models.StoreTheme).filter_by(store_id=totem.store_id).first()
            if theme:
                await sio.emit(
                    "theme_updated",
                    StoreThemeOut.model_validate(theme).model_dump(),
                    to=sid,
                )

            # Envia lista de produtos
            await refresh_product_list(db, totem.store_id, sid)

            # Envia os banners da loja
            banners = db.query(models.Banner).filter_by(store_id=totem.store_id).all()
            if banners:
                from src.api.shared_schemas.banner import BannerOut

                banner_payload = [BannerOut.model_validate(b).model_dump() for b in banners]
                await sio.emit("banners_updated", banner_payload, to=sid)

            orders = db.query(models.Order).filter_by(store_id=totem.store_id).order_by(models.Order.created_at.desc()).limit(20).all() # Exemplo: últimos 20 pedidos
            if orders:

                order_payload = [Order.model_validate(o).model_dump() for o in orders]
                await sio.emit("orders_initial", order_payload, to=sid)

# Evento de desconexão do Socket.IO
@sio.event
async def disconnect(sid, reason):
    print("disconnect", sid, reason)

    with get_db_manager() as db:
        totem = db.query(models.TotemAuthorization).filter_by(sid=sid).first()
        if totem:
            await sio.leave_room(sid, f"store_{totem.store_id}")
            totem.sid = None
            db.commit()






