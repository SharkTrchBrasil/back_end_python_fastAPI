from urllib.parse import parse_qs
import traceback
from src.core.database import get_db_manager
from src.core import models
from src.core.security import verify_access_token
from src.socketio_instance import sio


@sio.event(namespace="/admin")
async def connect(sid, environ, auth):
    try:
        print(f"\n[SOCKET ADMIN] Tentando conectar: SID={sid}")

        token = None
        if auth:
            token = auth.get("token_admin")
            print(f"[SOCKET ADMIN] Token recebido via 'auth': {token}")
        else:
            query = parse_qs(environ.get("QUERY_STRING", ""))
            token = query.get("token_admin", [None])[0]
            print(f"[SOCKET ADMIN] Token recebido via query string: {token}")

        if not token:
            print(f"[SOCKET ADMIN] Token ausente para SID {sid}")
            raise ConnectionRefusedError("Missing admin token")

        with get_db_manager() as db:
            email = verify_access_token(token)
            if not email:
                print(f"[SOCKET ADMIN] Token inválido ou expirado para SID {sid}")
                raise ConnectionRefusedError("Invalid or expired token")

            print(f"[SOCKET ADMIN] Token válido. Email extraído: {email}")
            admin = db.query(models.User).filter_by(email=email).first()

            if not admin:
                print(f"[SOCKET ADMIN] Usuário '{email}' não encontrado no banco.")
                raise ConnectionRefusedError("Admin not found")

            print(f"[SOCKET ADMIN] Usuário encontrado: {admin.email} (ID: {admin.id})")

            access = db.query(models.StoreAccess).filter_by(user_id=admin.id).first()

            if not access:
                print(f"[SOCKET ADMIN] Acesso à loja não encontrado para o usuário '{admin.email}'")
                raise ConnectionRefusedError("Admin store access not found")

            if not access.store_id:
                print(f"[SOCKET ADMIN] Admin '{admin.email}' não vinculado a nenhuma loja.")
                raise ConnectionRefusedError("Admin not linked to a store")

            if not access.role:
                print(f"[SOCKET ADMIN] Role com ID {access.role_id} não encontrada.")
                raise ConnectionRefusedError("Role não encontrada para este acesso.")

            room_name = f"store_{access.store_id}"

            admin.sid = sid
            db.commit()

            await sio.enter_room(sid, room_name, namespace="/admin")
            print(f"[SOCKET ADMIN] Admin '{admin.email}' conectado à sala: {room_name}")

            await sio.emit(
                "admin_connected",
                {
                    "status": "connected",
                    "store_id": access.store_id,
                    "admin_email": admin.email,
                },
                to=sid,
                namespace="/admin",
            )

            print(f"[SOCKET ADMIN] Evento 'admin_connected' enviado para SID {sid} com sucesso.\n")

    except ConnectionRefusedError as e:
        print(f"[SOCKET ADMIN] Conexão recusada para SID {sid}: {e}\n")
        raise
    except Exception as e:
        print(f"[SOCKET ADMIN] Erro inesperado durante conexão do SID {sid}: {e}")
        traceback.print_exc()
        raise ConnectionRefusedError("Internal server error during socket admin connect")


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
