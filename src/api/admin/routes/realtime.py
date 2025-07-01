from urllib.parse import parse_qs
import traceback
from src.core.database import get_db_manager
from src.core import models
from src.core.security import verify_access_token
from src.socketio_instance import sio


@sio.event(namespace="/admin")
async def connect(sid, environ, auth):
    try:
        print(f"\n[SOCKET][CONNECT] SID {sid} - Iniciando conexão...")

        token = None
        if auth:
            token = auth.get("token_admin")
            print(f"[SOCKET] Token via auth: {token}")
        else:
            query = parse_qs(environ.get("QUERY_STRING", ""))
            token = query.get("token_admin", [None])[0]
            print(f"[SOCKET] Token via query string: {token}")

        if not token:
            print(f"[SOCKET][ERROR] Token ausente.")
            raise ConnectionRefusedError("Missing admin token")

        with get_db_manager() as db:
            email = verify_access_token(token)
            print(f"[SOCKET] Email do token: {email}")

            if not email:
                print(f"[SOCKET][ERROR] Token inválido.")
                raise ConnectionRefusedError("Invalid or expired token")

            admin = db.query(models.User).filter_by(email=email).first()
            print(f"[SOCKET] Admin encontrado: {admin}")

            if not admin:
                print(f"[SOCKET][ERROR] Admin não encontrado.")
                raise ConnectionRefusedError("Admin not found")

            access = db.query(models.StoreAccess).filter_by(user_id=admin.id).first()
            print(f"[SOCKET] Acesso à loja: {access}")

            if not access or not access.store_id:
                print(f"[SOCKET][ERROR] Admin sem acesso a nenhuma loja.")
                raise ConnectionRefusedError("Admin not linked to store")

            store_id = access.store_id
            print(f"[SOCKET] Loja vinculada: {store_id}")

            admin.sid = sid
            db.commit()
            print(f"[SOCKET] SID {sid} salvo.")

            room_name = f"store_{store_id}"
            await sio.enter_room(sid, room_name, namespace="/admin")
            print(f"[SOCKET] Entrou na sala: {room_name}")

            await sio.emit(
                "admin_connected",
                {
                    "status": "connected",
                    "store_id": store_id,
                    "admin_email": admin.email,
                },
                to=sid,
                namespace="/admin",
            )
            print(f"[SOCKET] Conexão confirmada para o cliente.")

    except ConnectionRefusedError as e:
        print(f"[SOCKET][REFUSED] SID {sid}: {e}")
        raise
    except Exception as e:
        print(f"[SOCKET][FATAL ERROR] SID {sid}: {e}")
        traceback.print_exc()
        raise ConnectionRefusedError(f"Erro interno do servidor: {e}")
