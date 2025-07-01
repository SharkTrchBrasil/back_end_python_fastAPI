from urllib.parse import parse_qs
from src.core import models
from src.core.database import get_db_manager
from src.core.models import User
from src.core.security import verify_access_token
from src.socketio_instance import sio




@sio.event(namespace="/admin")
async def connect(sid, environ, auth):
    try:
        token = auth.get('token_admin') if auth else None
        if not token:
            raise ConnectionRefusedError("Missing token")

        # autentique o token e extraia o email
        with get_db_manager() as db:
            email = verify_access_token(token)
            print(f"[SOCKET] Email extraído do token: {email}")

            if not email:
                print("[SOCKET] Token inválido ou expirado")
                raise ConnectionRefusedError("Token inválido ou expirado")

            admin = db.query(User).filter_by(email=email).first()
            print(f"[SOCKET] Admin encontrado: {admin}")

            if not admin:
                print("[SOCKET] Admin não encontrado no banco")
                raise ConnectionRefusedError("Admin não encontrado")

            if not admin.store_id:
                print("[SOCKET] Admin sem store_id")
                raise ConnectionRefusedError("Admin não vinculado a loja")

            room = f"store_{admin.store_id}"
            await sio.enter_room(sid, room, namespace="/admin")

            admin.sid = sid
            db.commit()

            print(f"[SOCKET] Admin {admin.email} (ID: {admin.id}) entrou na sala {room}")

    except Exception as e:
        import traceback
        print("[SOCKET] Erro durante connect_admin:")
        traceback.print_exc()
        raise ConnectionRefusedError("Erro interno ao conectar admin")





@sio.event(namespace="/admin")
async def disconnect(sid):
    with get_db_manager() as db:
        admin = db.query(User).filter_by(sid=sid).first()
        if admin and admin.store_id:
            await sio.leave_room(sid, f"store_{admin.store_id}", namespace="/admin")
            print(f"[Admin Disconnected] {admin.email} (ID: {admin.id}) saiu da sala store_{admin.store_id}")
            admin.sid = None
            db.commit()

