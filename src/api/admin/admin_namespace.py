# src/api/admin/admin_namespace.py
from urllib.parse import parse_qs

from socketio import AsyncNamespace

from src.core.database import get_db_manager
from src.api.admin.services.authorize_admin import authorize_admin, update_sid, enter_store_room


class AdminNamespace(AsyncNamespace):
    async def on_connect(self, sid, environ):
        query = parse_qs(environ.get('QUERY_STRING', ''))
        token = query.get('admin_token', [None])[0]  # Assume que o parâmetro é 'admin_token'

        if not token:
            raise ConnectionRefusedError("Token de acesso obrigatório")

        with get_db_manager() as db:
            # Usa a função authorize_admin existente
            totem = await authorize_admin(db, token)
            if not totem:
                raise ConnectionRefusedError("Credenciais inválidas ou não autorizadas")

            # Atualiza SID usando a função existente
            await update_sid(db, totem, sid)

            # Entra na room usando a função existente
            room_name = await enter_store_room(sid, totem.store.id)
            print(f'✅ Admin conectado (Totem ID: {totem.id}, Loja: {totem.store.id}, Room: {room_name})')

            # Emite eventos iniciais
            await self.emit('connection_success', {
                'message': 'Autenticado com sucesso',
                'store_id': totem.store.id
            }, to=sid)

    async def on_disconnect(self, sid):
        print(f'🔌 Admin desconectado: {sid}')
        # Limpeza pode ser adicionada aqui se necessário