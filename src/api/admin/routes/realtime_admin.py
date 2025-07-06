from urllib.parse import parse_qs



from src.api.admin.events.admin_socketio_emitters import (
    emit_orders_initial,
    product_list_all,
    emit_store_full_updated,
)
from src.api.admin.services.authorize_admin import authorize_admin, update_sid

from src.core import models
from src.core.database import get_db_manager

from src.socketio_instance import sio


@sio.event
async def connect(sid, environ):
    print(f"[SOCKET.IO] ✅ Nova conexão admin: {sid}")
    query = parse_qs(environ.get("QUERY_STRING", ""))
    token = query.get("admin_token", [None])[0]  # Parâmetro deve ser 'admin_token'

    if not token:
        raise ConnectionRefusedError("Token de acesso obrigatório")

    with get_db_manager() as db:
        # Usa sua função authorize_admin existente (que verifica totem_authorizations)
        totem = await authorize_admin(db, token)
        if not totem or not totem.store:
            raise ConnectionRefusedError("Credenciais inválidas ou acesso não autorizado")

        # Atualiza o SID (se necessário)
        await update_sid(db, totem, sid)

        # Room específica para admin (agora usando store_id do totem)
        room_name = f"admin_store_{totem.store.id}"
        await sio.enter_room(sid, room_name)
        print(f"[SOCKET.IO] Conexão autorizada (Totem ID: {totem.id}, Loja: {totem.store.id})")

        # Emite dados iniciais (ajuste os emitters conforme necessário)
        await emit_store_full_updated(db, totem.store.id, sid)
        await product_list_all(db, totem.store.id, sid)
        await emit_orders_initial(db, totem.store.id, sid)
# Evento de desconexão do Socket.IO
@sio.event
async def disconnect(sid, reason):

    with get_db_manager() as db:
        totem = db.query(models.TotemAuthorization).filter_by(sid=sid).first()
        if totem:
            await sio.leave_room(sid, f"store_{totem.store_id}")
            totem.sid = None
            db.commit()




