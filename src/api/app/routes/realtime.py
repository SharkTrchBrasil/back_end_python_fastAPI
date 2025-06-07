from urllib.parse import parse_qs

import socketio
from sqlalchemy.orm import joinedload

from src.api.app.schemas.store_details import StoreDetails
from src.api.shared_schemas.product import ProductOut
from src.api.shared_schemas.store_theme import StoreTheme
from src.core import models
from src.core.database import get_db_manager

# Configura o servidor Socket.IO
sio = socketio.AsyncServer(
    cors_allowed_origins='*',
    logger=True,
    engineio_logger=True,
    async_mode="asgi"
)

# Função para emitir a lista de produtos atualizada
async def refresh_product_list(db, store_id: int, sid: str | None = None):
    products = db.query(models.Product).options(
        joinedload(models.Product.variant_links)
            .joinedload(models.ProductVariantProduct.variant)
            .joinedload(models.Variant.options)
    ).filter_by(store_id=store_id, available=True).all()

    payload = [
        ProductOut.model_validate(product).model_dump(exclude_unset=True)
        for product in products
    ]

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

            # Envia tema da loja (se houver)
            theme = db.query(models.StoreTheme).filter_by(store_id=totem.store_id).first()
            if theme:
                await sio.emit('theme_updated', StoreTheme.model_validate(theme, from_attributes=True).model_dump(),
                               to=sid)

            # Envia lista de produtos
            await refresh_product_list(db, totem.store_id, sid)


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
