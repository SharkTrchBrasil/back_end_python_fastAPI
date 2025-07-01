from urllib.parse import parse_qs
import traceback
from sqlalchemy.orm import joinedload # Import this for eager loading

from src.core.database import get_db_manager
from src.core import models # Assuming your models are in src.core.models
from src.core.security import verify_access_token
from src.socketio_instance import sio

from src.api.shared_schemas.store_theme import StoreThemeOut # Make sure this path is correct
from src.api.shared_schemas.banner import BannerOut # Make sure this path is correct


# --- Evento de conexão do Socket.IO para administradores ---
@sio.event(namespace="/admin")
async def connect(sid, environ, auth):
    try:
        token = None
        # Prioriza o token no objeto 'auth' (Flutter e web clients modernos)
        if auth:
            token = auth.get("token_admin")
        else:
            # Fallback para o token na query string (compatibilidade)
            query = parse_qs(environ.get("QUERY_STRING", ""))
            token = query.get("token_admin", [None])[0]

        if not token:
            print(f"[ADMIN SOCKET] SID {sid}: Token de acesso admin ausente.")
            raise ConnectionRefusedError("Missing admin token")

        with get_db_manager() as db:
            email = verify_access_token(token)
            if not email:
                print(f"[ADMIN SOCKET] SID {sid}: Token inválido ou expirado para o admin.")
                raise ConnectionRefusedError("Invalid or expired token")

            # Carrega o usuário admin e se certifica de que ele tem um store_id
            admin = db.query(models.User).filter_by(email=email).first()

            if not admin:
                print(f"[ADMIN SOCKET] SID {sid}: Admin '{email}' não encontrado.")
                raise ConnectionRefusedError("Admin not found")

            if not admin.store_id:
                print(f"[ADMIN SOCKET] SID {sid}: Admin '{email}' não está vinculado a uma loja.")
                raise ConnectionRefusedError("Admin not linked to a store")

            # Atualiza o SID do admin no banco de dados
            admin.sid = sid
            db.commit()

            # Entra na sala específica da loja
            room_name = f"store_{admin.store_id}"
            await sio.enter_room(sid, room_name, namespace="/admin")

            print(f"[ADMIN SOCKET] Admin '{email}' (SID: {sid}) conectado à sala '{room_name}'.")



            # Confirmação final da conexão para o cliente admin
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

    except ConnectionRefusedError as e:
        # Erros esperados de recusa de conexão (token ausente/inválido, admin não encontrado, etc.)
        print(f"[ADMIN SOCKET] Conexão recusada para SID {sid}: {e}")
        raise # Relança a exceção para que o Socket.IO lide com a recusa.
    except Exception as e:
        # Captura qualquer outra exceção inesperada e imprime o traceback
        print(f"[ADMIN SOCKET] Erro inesperado durante a conexão para SID {sid}: {e}")
        traceback.print_exc()
        raise ConnectionRefusedError(f"Erro interno do servidor: {e}") # Relança como recusa de conexão

# --- Evento de desconexão do Socket.IO para administradores ---
@sio.event(namespace="/admin")
async def disconnect(sid):
    print(f"[ADMIN SOCKET] Desconexão: SID {sid}")
    with get_db_manager() as db:
        # Encontra o admin pelo SID para limpar o registro
        admin = db.query(models.User).filter_by(sid=sid).first()
        if admin:
            # Deixa a sala da loja
            room_name = f"store_{admin.store_id}"
            await sio.leave_room(sid, room_name, namespace="/admin")
            # Limpa o SID no banco de dados
            admin.sid = None
            db.commit()
            print(f"[ADMIN SOCKET] Admin '{admin.email}' (SID: {sid}) desconectado e SID limpo.")
        else:
            print(f"[ADMIN SOCKET] Cliente desconectado (SID: {sid}) não encontrado como admin.")