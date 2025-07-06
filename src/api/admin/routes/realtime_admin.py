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
    print(f"[SOCKET.IO] ✅ Novo admin conectado: {sid}")
    query = parse_qs(environ.get("QUERY_STRING", ""))
    token = query.get("admin_token", [None])[0]  # Renomeado para admin_token

    if not token:
        raise ConnectionRefusedError("Token de admin ausente")

    with get_db_manager() as db:
        admin = await authorize_admin(db, token)  # Assume que authorize_admin verifica credenciais de admin
        if not admin:
            raise ConnectionRefusedError("Token de admin inválido ou não autorizado")

        # Room específica para admin (opcional, se quiser segregar por loja)
        room_name = f"admin_store_{admin.store_id}"
        await sio.enter_room(sid, room_name)
        print(f"[SOCKET.IO] Admin entrou na room: {room_name}")

        # Emite dados iniciais
        await emit_store_full_updated(db, admin.store_id, sid)
        await product_list_all(db, admin.store_id, sid)
        await emit_orders_initial(db, admin.store_id, sid)


# Evento de desconexão do Socket.IO
@sio.event
async def disconnect(sid, reason):

    with get_db_manager() as db:
        totem = db.query(models.TotemAuthorization).filter_by(sid=sid).first()
        if totem:
            await sio.leave_room(sid, f"store_{totem.store_id}")
            totem.sid = None
            db.commit()




