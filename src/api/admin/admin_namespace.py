from urllib.parse import parse_qs

from socketio import AsyncNamespace

from src.api.admin.routes.realtime_admin import emit_initial_data
from src.core.database import get_db_manager
from src.api.admin.services.authorize_admin import authorize_admin, update_sid



class AdminNamespace(AsyncNamespace):
    async def on_connect(self, sid, environ):
        print(f"[ADMIN] Conexão estabelecida: {sid}")
        query = parse_qs(environ.get('QUERY_STRING', ''))
        token = query.get('admin_token', [None])[0]

        if not token:
            raise ConnectionRefusedError("Token ausente")

        with get_db_manager() as db:
            totem = await authorize_admin(db, token)
            if not totem or not totem.store:
                raise ConnectionRefusedError("Acesso negado")

            await update_sid(db, totem, sid)
            await self.enter_room(sid, f"admin_store_{totem.store.id}")

            # Chama os emitters globais
            await emit_initial_data(db, totem.store.id, sid)