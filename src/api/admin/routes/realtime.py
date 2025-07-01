
from src.core import models

from src.socketio_instance import sio

from urllib.parse import parse_qs
from src.core.security import verify_access_token
from src.core.database import get_db_manager


@sio.event(namespace="/admin")
async def connect(sid, environ, auth):
    print(f"[SOCKET ADMIN] Tentando conectar SID={sid} auth={auth}")

    token = auth.get("token_admin") if auth else None
    store_id = int(auth.get("store_id")) if auth and auth.get("store_id") else None

    if not token or not store_id:
        print("[SOCKET ADMIN] Token ou store_id ausente!")
        raise ConnectionRefusedError("Missing token or store_id")

    print("[SOCKET ADMIN] Conectado com token e store_id (teste, sem DB)")
    await sio.enter_room(sid, f"store_{store_id}", namespace="/admin")
    await sio.emit("admin_connected", {"status": "connected", "store_id": store_id}, to=sid, namespace="/admin")


@sio.event(namespace="/admin")
async def disconnect(sid):
    print(f"[ADMIN SOCKET] Desconexão detectada: SID {sid}")

    with get_db_manager() as db:
        # Busca o usuário que possui esse SID
        admin = db.query(models.User).filter_by(sid=sid).first()

        if admin:
            # Busca o acesso do admin para saber qual loja ele está vinculado
            access = db.query(models.StoreAccess).filter_by(user_id=admin.id).first()

            if access and access.store_id:
                room_name = f"store_{access.store_id}"
                await sio.leave_room(sid, room_name, namespace="/admin")
                print(f"[ADMIN SOCKET] Admin '{admin.email}' saiu da sala '{room_name}'.")

            # Limpa o SID do admin no banco de dados
            admin.sid = None
            db.commit()
            print(f"[ADMIN SOCKET] SID limpo para o admin '{admin.email}'.")

        else:
            print(f"[ADMIN SOCKET] Nenhum admin com SID {sid} encontrado.")
