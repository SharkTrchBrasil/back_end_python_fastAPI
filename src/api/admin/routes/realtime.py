from urllib.parse import parse_qs
import traceback
from src.core.database import get_db_manager
from src.core import models
from src.core.security import verify_access_token
from src.socketio_instance import sio


@sio.event(namespace="/admin")
async def connect(sid, environ, auth):
    try:
        print(f"\n[ADMIN SOCKET] Iniciando conexão para SID: {sid}")

        token = None

        if auth:
            token = auth.get("token_admin")
            print(f"[DEBUG] Token recebido via 'auth': {token}")
        else:
            query = parse_qs(environ.get("QUERY_STRING", ""))
            token = query.get("token_admin", [None])[0]
            print(f"[DEBUG] Token recebido via query string: {token}")

        if not token:
            print(f"[ADMIN SOCKET] SID {sid}: Token de acesso admin ausente.")
            raise ConnectionRefusedError("Missing admin token")

        with get_db_manager() as db:
            email = verify_access_token(token)
            if not email:
                print(f"[ADMIN SOCKET] Token inválido.")
                raise ConnectionRefusedError("Invalid or expired token")

            admin = db.query(models.User).filter_by(email=email).first()
            if not admin:
                print(f"[ADMIN SOCKET] Admin '{email}' não encontrado.")
                raise ConnectionRefusedError("Admin not found")

            # Busca o acesso à loja (store_accesses)
            access = db.query(models.StoreAccess).filter_by(user_id=admin.id).first()
            if not access:
                print(f"[ADMIN SOCKET] Admin '{email}' não possui acesso a nenhuma loja.")
                raise ConnectionRefusedError("Admin not linked to any store")

            store_id = access.store_id  # <-- Esse é o que você deve usar

            # Salva o SID
            admin.sid = sid
            db.commit()

            room_name = f"store_{store_id}"
            await sio.enter_room(sid, room_name, namespace="/admin")

            print(f"[ADMIN SOCKET] Admin '{email}' (SID: {sid}) conectado à sala '{room_name}'.")

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
            print(f"[ADMIN SOCKET] Mensagem 'admin_connected' enviada para {sid}.")

    except ConnectionRefusedError as e:
        print(f"[ADMIN SOCKET] Conexão recusada para SID {sid}: {e}")
        raise
    except Exception as e:
        print(f"[ADMIN SOCKET] Erro inesperado durante a conexão para SID {sid}: {e}")
        traceback.print_exc()
        raise ConnectionRefusedError(f"Erro interno do servidor: {e}")
