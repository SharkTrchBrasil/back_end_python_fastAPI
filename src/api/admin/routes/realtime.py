from urllib.parse import parse_qs
from src.core import models
from src.core.database import get_db_manager
from src.core.models import User
from src.core.security import verify_access_token
from src.socketio_instance import sio



@sio.on("connect")



async def connect_admin(sid, environ):
    print("Namespaces registrados:", sio.namespaces)
    try:
        query_string = environ.get("QUERY_STRING", "")
        print(f"[SOCKET] QUERY_STRING: {query_string}")
        query = parse_qs(query_string)
        token = query.get("token_admin", [None])[0]
        print(f"[SOCKET] Token recebido: {token}")

        if not token:
            print("[SOCKET] Token ausente")
            raise ConnectionRefusedError("Token do admin ausente")

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





@sio.on("disconnect", namespace="/admin")
async def disconnect_admin(sid):
    with get_db_manager() as db:
        admin = db.query(models.User).filter_by(sid=sid).first()
        if admin and admin.store_id:
            await sio.leave_room(sid, f"store_{admin.store_id}", namespace="/admin")
            print(f"[Admin Disconnected] {admin.email} (ID: {admin.id}) saiu da sala store_{admin.store_id}")
            admin.sid = None
            db.commit()
