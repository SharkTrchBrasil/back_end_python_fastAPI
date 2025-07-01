
import traceback
from urllib.parse import parse_qs
from src.core.database import get_db_manager
from src.core.models import User
from src.core.security import verify_access_token
from src.socketio_instance import sio


@sio.event(namespace="/admin")
async def connect(sid, environ):
    try:
        query = parse_qs(environ.get("QUERY_STRING", ""))
        token = query.get("token_admin", [None])[0]

        if not token:
            raise ConnectionRefusedError("Token não fornecido")

        with get_db_manager() as db:
            email = verify_access_token(token)

            if not email:
                print("[ADMIN SOCKET] Token inválido ou expirado.")
                raise ConnectionRefusedError("Token inválido ou expirado")

            admin = db.query(User).filter_by(email=email).first()

            if not admin:
                print("[ADMIN SOCKET] Admin não encontrado.")
                raise ConnectionRefusedError("Admin não encontrado")

            if not admin.store_id:
                print("[ADMIN SOCKET] Admin sem loja vinculada.")
                raise ConnectionRefusedError("Admin sem loja vinculada")

            # Entra na sala da loja
            room = f"store_{admin.store_id}"
            await sio.enter_room(sid, room, namespace="/admin")

            # Atualiza o SID no banco
            admin.sid = sid
            db.commit()

            print(f"[ADMIN SOCKET] Admin {email} conectado à sala {room}")

            # Confirmação para o cliente
            await sio.emit("admin_connected", {
                "status": "connected",
                "store_id": admin.store_id,
                "admin_email": admin.email,
            }, to=sid, namespace="/admin")

    except Exception as e:
        print(f"[ADMIN SOCKET] Erro ao conectar: {e}")
        traceback.print_exc()
        raise ConnectionRefusedError("Erro interno durante a conexão")


@sio.event(namespace="/admin")
async def disconnect(sid):
    print(f"[ADMIN SOCKET] Desconexão: {sid}")

    with get_db_manager() as db:
        admin = db.query(User).filter_by(sid=sid).first()

        if admin and admin.store_id:
            await sio.leave_room(sid, f"store_{admin.store_id}", namespace="/admin")
            print(f"[ADMIN SOCKET] Admin {admin.email} saiu da sala store_{admin.store_id}")
            admin.sid = None
            db.commit()
