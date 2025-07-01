
from src.core import models
from src.core.helpers.authorize_totem import authorize_totem

from src.socketio_instance import sio


from src.core.database import get_db_manager
from urllib.parse import parse_qs


@sio.event
async def connect(sid, environ):
    query = parse_qs(environ.get("QUERY_STRING", ""))
    token = query.get("totem_token", [None])[0]

    if not token:
        raise ConnectionRefusedError("Missing token")

    with get_db_manager() as db:
        totem = await authorize_totem(db, token)
        if not totem:
            raise ConnectionRefusedError("Invalid or unauthorized token")

        totem.sid = sid
        db.commit()

        room_name = f"store_{totem.store_id}"
        await sio.enter_room(sid, room_name)

        await sio.emit("admin_connected", {"store_id": totem.store_id}, to=sid)

@sio.event
async def disconnect(sid):
    with get_db_manager() as db:
        totem = db.query(models.TotemAuthorization).filter_by(sid=sid).first()
        if totem:
            await sio.leave_room(sid, f"store_{totem.store_id}")
            totem.sid = None
            db.commit()

@sio.event
async def order_created(sid, data):
    print(f"Pedido recebido: {data}")
    # Aqui você pode processar o pedido ou simplesmente emitir para a sala da loja:
    with get_db_manager() as db:
        totem = db.query(models.TotemAuthorization).filter_by(sid=sid).first()
        if not totem:
            print("Totem não autorizado")
            return

        room_name = f"store_{totem.store_id}"
        await sio.emit("order_created", data, to=room_name)
