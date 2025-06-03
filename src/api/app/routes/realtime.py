from urllib.parse import parse_qs

import socketio
from sqlalchemy.orm import selectinload, joinedload

from src.api.app.schemas.product import Product
from src.api.app.schemas.store import Store, StoreTheme
from src.core import models
from src.core.database import get_db_manager

sio = socketio.AsyncServer(cors_allowed_origins='*', logger=True, engineio_logger=True, async_mode="asgi")


async def refresh_product_list(db, store_id, sid: str | None = None):
    products = db.query(models.Product).options(
        joinedload(models.Product.variant_links).joinedload(models.ProductVariantProduct.variant)
    ).filter_by(store_id=store_id, available=True).all()

    if sid:
        await sio.emit('products_updated', [Product.model_validate(product).model_dump() for product in products], to=sid)
    else:
        await sio.emit('products_updated', [Product.model_validate(product).model_dump() for product in products], to=f"store_{store_id}")


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

        totem.sid = sid
        db.commit()

        room_name = f"store_{totem.store_id}"
        await sio.enter_room(sid, room_name)

        # Emitir informações da loja
        await sio.emit('store_updated', Store.model_validate(totem.store).model_dump(), to=sid)

        # Emitir tema, se houver
        theme = db.query(models.StoreTheme).filter(
            models.StoreTheme.store_id == totem.store_id
        ).first()

        if theme:
            await sio.emit('theme_updated', StoreTheme.model_validate(theme).model_dump(), to=sid)

        # Atualizar a lista de produtos
        await refresh_product_list(db, totem.store_id, sid)






@sio.event
async def disconnect(sid, reason):
    print('disconnect ', sid, reason)

    with get_db_manager() as db:
        totem = db.query(models.TotemAuthorization).filter(models.TotemAuthorization.sid == sid).first()
        if totem:
            await sio.leave_room(sid, f"store_{totem.store_id}")

            totem.sid = None
            db.commit()
