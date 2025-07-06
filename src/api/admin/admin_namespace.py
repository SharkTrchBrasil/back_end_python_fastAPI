# src/admin_namespace.py
from socketio import AsyncNamespace
from urllib.parse import parse_qs
from src.core.database import get_db_manager
from src.api.admin.services.authorize_admin import authorize_admin


class AdminNamespace(AsyncNamespace):
    def __init__(self, namespace):
        super().__init__(namespace)
        self.connected_admins = {}  # {sid: admin_id}

    async def on_connect(self, sid, environ):
        query = parse_qs(environ.get('QUERY_STRING', ''))
        token = query.get('token', [None])[0]

        if not token:
            raise ConnectionRefusedError("Token de admin obrigatório")

        with get_db_manager() as db:
            admin = await authorize_admin(db, token)
            if not admin:
                raise ConnectionRefusedError("Admin não autorizado")

            # Armazena a conexão
            self.connected_admins[sid] = admin.id
            await self.enter_room(sid, f'admin_store_{admin.store_id}')
            print(f'✅ Admin {admin.id} conectado (SID: {sid})')

            # Emite confirmação
            await self.emit('auth_success', {'message': 'Conectado'}, to=sid)

    async def on_disconnect(self, sid):
        if sid in self.connected_admins:
            print(f'🔌 Admin {self.connected_admins[sid]} desconectado')
            del self.connected_admins[sid]