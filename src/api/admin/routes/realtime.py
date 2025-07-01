from urllib.parse import parse_qs
from src.core import models
from src.core.database import get_db_manager
from src.core.models import User
from src.core.security import verify_access_token
from src.socketio_instance import sio

@sio.on("connect", namespace="/admin")
async def connect_admin(sid, environ):
    try:
        query_string = environ.get("QUERY_STRING", "")
        query = parse_qs(query_string)
        token = query.get("token_admin", [None])[0]

        print(f"[Socket.IO] Nova conexão admin | SID: {sid}")
        print(f"[Socket.IO] QUERY_STRING recebida: {query_string}")

        if not token:
            raise ConnectionRefusedError("Token do admin ausente")

        with get_db_manager() as db:
            email = verify_access_token(token)
            if not email:
                raise ConnectionRefusedError("Token inválido ou expirado")

            admin = db.query(User).filter_by(email=email).first()
            if not admin:
                raise ConnectionRefusedError("Admin não encontrado")

            if not admin.store_id:
                raise ConnectionRefusedError("Admin não vinculado a loja")

            room = f"store_{admin.store_id}"
            await sio.enter_room(sid, room, namespace="/admin")

            admin.sid = sid
            db.commit()

            print(f"[Admin Connected] {admin.email} (ID: {admin.id}) entrou na sala {room}")
    except Exception as e:
        import traceback
        print("[Socket.IO] Erro durante connect_admin:")
        traceback.print_exc()
        raise ConnectionRefusedError("Erro interno ao conectar admin")

@sio.on("disconnect", namespace="/admin")
async def disconnect_admin(sid):
    with get_db_manager() as db:
        admin = db.query(models.User).filter_by(sid=sid).first()
        if admin and admin.store_id:
            await sio.leave_room(sid, f"store_{admin.store_id}", namespace="/admin")
            print(f"[Admin Disconnected] {admin.email} (ID: {admin.id}) saiu da sala store_{admin.store_id}")
            admin.sid = None
            db.commit()
