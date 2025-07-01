from urllib.parse import parse_qs
from src.core import models
from src.core.database import get_db_manager
from src.core.models import User
from src.core.security import verify_access_token
from src.socketio_instance import sio


@sio.event(namespace="/admin")
async def connect(sid, environ, auth):
    try:
        # Obter o token tanto do auth quanto da query string (para compatibilidade)
        query = parse_qs(environ.get("QUERY_STRING", ""))
        token = auth.get('token_admin') if auth else query.get("token_admin", [None])[0]

        if not token:
            raise ConnectionRefusedError("Missing token")

        with get_db_manager() as db:
            email = verify_access_token(token)
            print(f"[ADMIN SOCKET] Email do token: {email}")

            if not email:
                raise ConnectionRefusedError("Token inválido ou expirado")

            admin = db.query(User).filter_by(email=email).first()
            if not admin:
                raise ConnectionRefusedError("Admin não encontrado")

            if not admin.store_id:
                raise ConnectionRefusedError("Admin não vinculado a loja")

            # Entra na sala
            room = f"store_{admin.store_id}"
            await sio.enter_room(sid, room, namespace="/admin")
            admin.sid = sid
            db.commit()

            print(f"[ADMIN SOCKET] Admin {email} conectado à sala {room}")

            # Envia dados iniciais (similar ao app que funciona)
            store = db.query(models.Store).options(
                joinedload(models.Store.payment_methods),
                joinedload(models.Store.delivery_config),
            ).filter_by(id=admin.store_id).first()

            if store:
                await sio.emit("admin_connected", {
                    "store_id": store.id,
                    "store_name": store.name,
                    "admin_email": email
                }, to=sid, namespace="/admin")

    except Exception as e:
        print(f"[ADMIN SOCKET ERROR] {str(e)}")
        raise ConnectionRefusedError("Falha na conexão: " + str(e))



@sio.event(namespace="/admin")
async def disconnect(sid):
    with get_db_manager() as db:
        admin = db.query(User).filter_by(sid=sid).first()
        if admin and admin.store_id:
            await sio.leave_room(sid, f"store_{admin.store_id}", namespace="/admin")
            print(f"[Admin Disconnected] {admin.email} (ID: {admin.id}) saiu da sala store_{admin.store_id}")
            admin.sid = None
            db.commit()

