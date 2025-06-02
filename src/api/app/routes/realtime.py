import socketio

from src.api.admin.schemas.product import Product
from src.api.admin.schemas.store import Store
from src.api.admin.schemas.store_theme import StoreTheme
from src.core import models
from src.core.database import get_db_manager

sio = socketio.AsyncServer(cors_allowed_origins='*', logger=True, engineio_logger=True, async_mode="asgi")

#@sio.event
#def apply_coupon(sid, data):
    #with get_db_manager() as db:
        #totem = db.query(models.TotemAuthorization).filter(models.TotemAuthorization.sid == sid,
                                                           #models.TotemAuthorization.granted.is_(True)).first()

async def refresh_product_list(db, store_id, sid: str | None = None):
    products = db.query(models.Product).filter_by(store_id=store_id, available=True).all()

    if sid:
        await sio.emit('products_updated', [Product.model_validate(product).model_dump() for product in products], to=sid)
    else:
        await sio.emit('products_updated', [Product.model_validate(product).model_dump() for product in products], to=f"store_{store_id}")


@sio.event
async def connect(sid, environ):
    print('connect ', sid)

    token = environ.get('HTTP_TOTEM_TOKEN')

    with get_db_manager() as db:
        totem = db.query(models.TotemAuthorization).filter(models.TotemAuthorization.totem_token == token,
                                                    models.TotemAuthorization.granted.is_(True)).first()
        if not totem:
            print('REJECT CONNECTION')
            raise ConnectionRefusedError('Authentication failed')

        totem.sid = sid
        db.commit()

        await sio.enter_room(sid, f"store_{totem.store_id}")

        await sio.emit('store_updated', Store.model_validate(totem.store).model_dump(), to=sid)

        theme = db.query(models.StoreTheme).filter(models.StoreTheme.store_id == totem.store_id).first()

        if theme:
            await sio.emit('theme_updated', StoreTheme.model_validate(theme).model_dump(), to=sid)

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
