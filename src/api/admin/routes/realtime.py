import traceback
from urllib.parse import parse_qs
from src.core import models
from src.core.database import get_db_manager
from src.core.models import User
from src.core.security import verify_access_token
from src.socketio_instance import sio

@sio.on("connect", namespace="/admin")
async def connect(sid, environ, auth):
    try:
        # Obter token via auth ou query string
        query = parse_qs(environ.get("QUERY_STRING", ""))
        token = auth.get('token_admin') if auth else query.get("token_admin", [None])[0]

        print(f"[ADMIN CONNECT] Tentativa de conexão - SID: {sid}")
        print(f"[ADMIN CONNECT] Token recebido: {token}")

        if not token:
            raise ConnectionRefusedError("Token não fornecido")

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

            print(f"[ADMIN CONNECT] Admin {email} conectado à sala {room}")

            await sio.emit('admin_connected', {
                'status': 'connected',
                'store_id': admin.store_id,
                'admin_email': email
            }, to=sid, namespace="/admin")

    except Exception as e:
        print(f"[ADMIN CONNECT ERROR] Erro na conexão: {str(e)}")
        traceback.print_exc()
        raise ConnectionRefusedError(f"Erro na conexão: {str(e)}")


@sio.event(namespace="/admin")
async def disconnect(sid):
    with get_db_manager() as db:
        admin = db.query(User).filter_by(sid=sid).first()
        if admin and admin.store_id:
            await sio.leave_room(sid, f"store_{admin.store_id}", namespace="/admin")
            print(f"[Admin Disconnected] {admin.email} (ID: {admin.id}) saiu da sala store_{admin.store_id}")
            admin.sid = None
            db.commit()

