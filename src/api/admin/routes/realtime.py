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
            print(f"[DEBUG] Verificando token com 'verify_access_token'...")
            email = verify_access_token(token)
            print(f"[DEBUG] Resultado do verify_access_token: {email}")

            if not email:
                print(f"[ADMIN SOCKET] SID {sid}: Token inválido ou expirado para o admin.")
                raise ConnectionRefusedError("Invalid or expired token")

            print(f"[DEBUG] Buscando admin no banco com email: {email}")
            admin = db.query(models.User).filter_by(email=email).first()
            print(f"[DEBUG] Resultado da consulta de admin: {admin}")

            if not admin:
                print(f"[ADMIN SOCKET] SID {sid}: Admin '{email}' não encontrado.")
                raise ConnectionRefusedError("Admin not found")

            print(f"[DEBUG] Verificando se o admin está vinculado a uma loja...")
            if not admin.store_id:
                print(f"[ADMIN SOCKET] SID {sid}: Admin '{email}' não está vinculado a uma loja.")
                raise ConnectionRefusedError("Admin not linked to a store")

            print(f"[DEBUG] Admin encontrado. Atualizando SID no banco de dados...")
            admin.sid = sid
            db.commit()
            print(f"[DEBUG] SID atualizado com sucesso.")

            room_name = f"store_{admin.store_id}"
            await sio.enter_room(sid, room_name, namespace="/admin")
            print(f"[ADMIN SOCKET] Admin '{email}' (SID: {sid}) conectado à sala '{room_name}'.")

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
            print(f"[ADMIN SOCKET] Mensagem 'admin_connected' enviada para {sid}.")

    except ConnectionRefusedError as e:
        print(f"[ADMIN SOCKET] Conexão recusada para SID {sid}: {e}")
        raise
    except Exception as e:
        print(f"[ADMIN SOCKET] Erro inesperado durante a conexão para SID {sid}: {e}")
        traceback.print_exc()
        raise ConnectionRefusedError(f"Erro interno do servidor: {e}")
