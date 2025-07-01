from urllib.parse import parse_qs
import traceback
from src.core.database import get_db_manager
from src.core.models import User
from src.core.security import verify_access_token
from src.socketio_instance import sio

@sio.event(namespace="/admin")
async def connect(sid, environ, auth):
    try:
        token = None
        if auth:
            token = auth.get("token_admin")
        else:
            query = parse_qs(environ.get("QUERY_STRING", ""))
            token = query.get("token_admin", [None])[0]

        if not token:
            raise ConnectionRefusedError("Missing token")

        with get_db_manager() as db:
            email = verify_access_token(token)
            if not email:
                raise ConnectionRefusedError("Invalid or expired token")

            admin = db.query(User).filter_by(email=email).first()
            if not admin:
                raise ConnectionRefusedError("Admin not found")

            if not admin.store_id:
                raise ConnectionRefusedError("Admin not linked to a store")

            room = f"store_{admin.store_id}"
            await sio.enter_room(sid, room, namespace="/admin")

            admin.sid = sid
            db.commit()

            print(f"[ADMIN SOCKET] Admin {email} connected to room {room}")

            await sio.emit(
                "admin_connected",
                {
                    "status": "connected",
                    "store_id": admin.store_id,
                    "admin_email": admin.email,
                },
                to=sid,
                namespace="/admin",
            )
    except Exception as e:
        print(f"[ADMIN SOCKET] Connection error: {e}")
        traceback.print_exc()
        raise ConnectionRefusedError(f"Connection error: {e}")
