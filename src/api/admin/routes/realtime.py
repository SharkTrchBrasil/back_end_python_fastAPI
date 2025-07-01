from urllib.parse import parse_qs
from src.core import models
from src.core.database import get_db_manager
from src.core.models import User
from src.core.security import verify_access_token
from src.socketio_instance import sio

@sio.on("connect", namespace="/admin")
async def connect_admin(sid, environ):
    print("\n========================")
    print("[Socket.IO] Início do connect_admin")
    print(f"[Socket.IO] SID: {sid}")
    print("========================")

    try:
        query_string = environ.get("QUERY_STRING", "")
        print(f"[Socket.IO] QUERY_STRING recebida: {query_string}")

        query = parse_qs(query_string)
        print(f"[Socket.IO] Query parseada: {query}")

        token = query.get("token_admin", [None])[0]
        print(f"[Socket.IO] Token extraído: {token}")

        if not token:
            print("[Socket.IO] Token ausente")
            raise ConnectionRefusedError("Token do admin ausente")

        print("[Socket.IO] Iniciando acesso ao banco de dados...")
        with get_db_manager() as db:
            email = verify_access_token(token)
            print(f"[Socket.IO] Email do token: {email}")

            if not email:
                print("[Socket.IO] Token inválido ou expirado")
                raise ConnectionRefusedError("Token inválido ou expirado")

            admin = db.query(User).filter_by(email=email).first()
            print(f"[Socket.IO] Admin encontrado: {admin}")

            if not admin:
                print("[Socket.IO] Admin não encontrado no banco")
                raise ConnectionRefusedError("Admin não encontrado")

            if not admin.store_id:
                print("[Socket.IO] Admin não tem store_id vinculado")
                raise ConnectionRefusedError("Admin não vinculado a loja")

            room = f"store_{admin.store_id}"
            print(f"[Socket.IO] Entrando na sala: {room}")

            await sio.enter_room(sid, room, namespace="/admin")

            print(f"[Socket.IO] Salvando SID {sid} no admin ID {admin.id}")
            admin.sid = sid
            db.commit()

            print(f"[Admin Connected] {admin.email} (ID: {admin.id}) entrou na sala {room}")
            print("[Socket.IO] Conexão finalizada com sucesso ✅")
    except Exception as e:
        import traceback
        print("[Socket.IO] ❌ Erro durante connect_admin:")
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
