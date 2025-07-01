from urllib.parse import parse_qs

from fastapi.encoders import jsonable_encoder
from sqlalchemy.orm import joinedload

from src.core import models
from src.core.database import get_db_manager
from src.api.app.schemas.order import Order
from src.core.models import User
from src.core.security import verify_access_token
from src.socketio_instance import sio


@sio.event
async def connect_admin(sid, environ):
    try:
        query = parse_qs(environ.get("QUERY_STRING", ""))
        token = query.get("token_admin", [None])[0]

        if not token:
            raise ConnectionRefusedError("Token do admin ausente")

        with get_db_manager() as db:
            email = verify_access_token(token)
            if not email:
                raise ConnectionRefusedError("Token inválido")

            admin = db.query(User).filter_by(email=email).first()
            if not admin:
                raise ConnectionRefusedError("Admin não encontrado")

            if not admin.store_id:
                raise ConnectionRefusedError("Admin não vinculado a loja")

            room = f"store_{admin.store_id}"
            await sio.enter_room(sid, room)

            admin.sid = sid  # Salva o sid do socket para desconexão
            db.commit()

            print(f"[Admin Connected] Admin {admin.id} entrou na sala {room}")
    except Exception as e:
        import traceback
        print("[Socket.IO] Erro durante connect_admin:")
        traceback.print_exc()
        raise ConnectionRefusedError("Erro interno ao conectar admin")


@sio.event
async def disconnect_admin(sid):
    with get_db_manager() as db:
        admin = db.query(models.User).filter_by(sid=sid).first()

        if admin and admin.store_id:
            await sio.leave_room(sid, f"store_{admin.store_id}")
            print(f"[Admin Disconnected] Admin {admin.id} saiu da sala store_{admin.store_id}")

            # Opcional: limpar o sid ao desconectar
            admin.sid = None
            db.commit()
