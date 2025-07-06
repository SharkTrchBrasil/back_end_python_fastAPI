from urllib.parse import parse_qs



from src.api.admin.events.admin_socketio_emitters import (
    emit_orders_initial,
    product_list_all,
    emit_store_full_updated,
)
from src.api.admin.services.authorize_admin import authorize_admin

from src.core import models
from src.core.database import get_db_manager

from src.socketio_instance import sio



@sio.event
async def connect(sid, environ):
    query = parse_qs(environ.get("QUERY_STRING", ""))
    token = query.get("totem_token", [None])[0]

    if not token:
        raise ConnectionRefusedError("Missing token")

    with get_db_manager() as db:
        totem = await authorize_admin(db, token)
        if not totem:
            raise ConnectionRefusedError("Invalid or unauthorized token")

        # Atualiza o SID do totem
        totem.sid = sid
        db.commit()

        room_name = f"store_{totem.store_id}"
        await sio.enter_room(sid, room_name)

        # Emite dados iniciais para o painel/admin
        await emit_store_full_updated(db, totem.store_id, sid)
        await product_list_all(db, totem.store_id, sid)
        await emit_orders_initial(db, totem.store_id, sid)


# Evento de desconexão do Socket.IO
@sio.event
async def disconnect(sid, reason):

    with get_db_manager() as db:
        totem = db.query(models.TotemAuthorization).filter_by(sid=sid).first()
        if totem:
            await sio.leave_room(sid, f"store_{totem.store_id}")
            totem.sid = None
            db.commit()
