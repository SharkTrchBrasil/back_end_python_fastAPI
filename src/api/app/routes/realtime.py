import socketio

from src.core import models
from src.core.database import get_db_manager

sio = socketio.AsyncServer(cors_allowed_origins='*', logger=True, engineio_logger=True, async_mode="asgi")

#@sio.event
#def apply_coupon(sid, data):
    #with get_db_manager() as db:
        #totem = db.query(models.TotemAuthorization).filter(models.TotemAuthorization.sid == sid,
                                                           #models.TotemAuthorization.granted.is_(True)).first()


@sio.event
async def connect(sid, environ):
    print('connect ', sid)

    await sio.emit('hello', 'world', to=sid)

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


@sio.event
def disconnect(sid, reason):
    print('disconnect ', sid, reason)
