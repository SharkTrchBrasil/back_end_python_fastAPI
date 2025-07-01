from urllib.parse import parse_qs
import traceback
from src.core.database import get_db_manager
from src.core import models
from src.core.security import verify_access_token
from src.socketio_instance import sio

from urllib.parse import parse_qs
from src.core.security import verify_access_token
from src.core.database import get_db_manager

@sio.event(namespace="/admin")
async def connect(sid, environ, auth):
    try:
        print(f"\n[SOCKET ADMIN] Tentando conectar: SID={sid}")

        # 1. Pegar o token da conexão (via auth ou query string)
        token = auth.get("token_admin") if auth else parse_qs(environ.get("QUERY_STRING", "")).get("token_admin", [None])[0]
        print(f"[SOCKET ADMIN] Token recebido: {token}")

        if not token:
            print(f"[SOCKET ADMIN] Token ausente para SID {sid}")
            raise ConnectionRefusedError("Missing admin token")

        # 2. Verifica e decodifica o token
        token_data = verify_access_token(token)
        if not token_data or "store_id" not in token_data:
            print(f"[SOCKET ADMIN] Token inválido ou sem store_id")
            raise ConnectionRefusedError("Invalid or expired token")

        store_id = token_data["store_id"]
        room_name = f"store_{store_id}"

        # 3. Entra na sala da loja
        await sio.enter_room(sid, room_name, namespace="/admin")
        print(f"[SOCKET ADMIN] Conectado à sala: {room_name}")

        # 4. Emite confirmação da conexão
        await sio.emit(
            "admin_connected",
            {
                "status": "connected",
                "store_id": store_id,
            },
            to=sid,
            namespace="/admin",
        )
        print(f"[SOCKET ADMIN] Evento 'admin_connected' enviado para SID {sid}.\n")

    except ConnectionRefusedError as e:
        print(f"[SOCKET ADMIN] Conexão recusada: {e}\n")
        raise
    except Exception as e:
        print(f"[SOCKET ADMIN] Erro inesperado: {e}")
        import traceback
        traceback.print_exc()
        raise ConnectionRefusedError("Internal error")




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
