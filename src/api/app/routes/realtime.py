from urllib.parse import parse_qs

import socketio
from sqlalchemy.orm import joinedload

from src.api.app.routes import products
from src.api.app.schemas.store_details import StoreDetails
from src.api.app.services.rating import get_ratings_summary

from src.api.shared_schemas.product import ProductOut
from src.api.shared_schemas.store_theme import StoreThemeOut

from src.core import models
from src.core.database import get_db_manager

# Configura o servidor Socket.IO
sio = socketio.AsyncServer(
    cors_allowed_origins='*',
    logger=True,
    engineio_logger=True,
    async_mode="asgi"
)


async def refresh_product_list(db, store_id: int, sid: str | None = None):
    products_l = db.query(models.Product).options(
        joinedload(models.Product.variant_links)
        .joinedload(models.ProductVariantProduct.variant)
        .joinedload(models.Variant.options)
    ).filter_by(store_id=store_id, available=True).all()

    payload = [ProductOut.from_orm_obj(product).model_dump(exclude_unset=True) for product in products_l]

    target = sid if sid else f"store_{store_id}"
    await sio.emit('products_updated', payload, to=target)


# Evento de conexão do Socket.IO
@sio.event
async def connect(sid, environ):
    query = parse_qs(environ.get('QUERY_STRING', ''))
    token = query.get('totem_token', [None])[0]

    if not token:
        raise ConnectionRefusedError('Missing token')

    with get_db_manager() as db:
        totem = db.query(models.TotemAuthorization).filter(
            models.TotemAuthorization.totem_token == token,
            models.TotemAuthorization.granted.is_(True)
        ).first()

        if not totem or not totem.store:
            raise ConnectionRefusedError('Invalid or unauthorized token')

        # Atualiza o SID do totem
        totem.sid = sid
        db.commit()

        room_name = f"store_{totem.store_id}"
        await sio.enter_room(sid, room_name)

        # Carrega dados completos da loja
        store = db.query(models.Store).options(
            joinedload(models.Store.payment_methods),
            joinedload(models.Store.delivery_config),
            joinedload(models.Store.hours),
            joinedload(models.Store.cities).joinedload(models.StoreCity.neighborhoods),
        ).filter_by(id=totem.store_id).first()

        if store:
            # Envia dados da loja
            await sio.emit(
                'store_updated',
                StoreDetails.model_validate(store).model_dump(),
                to=sid
            )

            theme = db.query(models.StoreTheme).filter_by(store_id=totem.store_id).first()
            if theme:
                await sio.emit(
                    'theme_updated',
                    StoreThemeOut.model_validate(theme).model_dump(),
                    to=sid
                )
            # Envia lista de produtos
            await refresh_product_list(db, totem.store_id, sid)

            # Envia os banners da loja
            banners = db.query(models.Banner).filter_by(store_id=totem.store_id).all()
            if banners:
                from src.api.shared_schemas.banner import BannerOut
                banner_payload = [BannerOut.model_validate(b).model_dump() for b in banners]
                await sio.emit('banners_updated', banner_payload, to=sid)

    # --- Envia avaliações da loja ---
    store_ratings_summary = get_ratings_summary(db, store_id=totem.store_id)
    await sio.emit('store_ratings_updated', store_ratings_summary, to=sid)

    # --- Envia avaliações dos produtos ---
    products_r = db.query(models.Product).filter_by(store_id=totem.store_id, available=True).all()
    product_ratings = {}
    for product in products_r:
        product_ratings[product.id] = get_ratings_summary(db, product_id=product.id)

    await sio.emit('product_ratings_updated', product_ratings, to=sid)

# Evento de desconexão do Socket.IO
@sio.event
async def disconnect(sid, reason):
    print('disconnect', sid, reason)

    with get_db_manager() as db:
        totem = db.query(models.TotemAuthorization).filter_by(sid=sid).first()
        if totem:
            await sio.leave_room(sid, f"store_{totem.store_id}")
            totem.sid = None
            db.commit()
