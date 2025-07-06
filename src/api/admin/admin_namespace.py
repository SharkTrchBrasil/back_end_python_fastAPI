from urllib.parse import parse_qs

from src.api.admin.services.authorize_admin import enter_store_room, authorize_admin, update_sid
from src.core.database import get_db_manager


async def on_connect(self, sid, environ):
    print(f"[SOCKET.IO] ✅ Tentativa de conexão admin: {sid}")
    query = parse_qs(environ.get("QUERY_STRING", ""))
    token = query.get("admin_token", [None])[0]

    if not token:
        raise ConnectionRefusedError("Token de admin ausente")

    with get_db_manager() as db:
        try:
            # 1. Autenticação
            totem = await authorize_admin(db, token)
            if not totem or not totem.store:
                raise ConnectionRefusedError("Credenciais inválidas")

            # 2. Atualização do SID
            await update_sid(db, totem, sid)

            # 3. Entrar na room COM NAMESPACE EXPLÍCITO
            room_name = await enter_store_room(sid, totem.store.id, self.namespace)

            # 4. Emitir dados iniciais
            await self.emit('connection_ack', {
                'status': 'authenticated',
                'store_id': totem.store.id
            }, to=sid)

            print(f"🟢 [SOCKET.IO] Admin autenticado (SID: {sid}, Loja: {totem.store.id})")

        except Exception as e:
            print(f"🔴 [SOCKET.IO] Erro na conexão: {str(e)}")
            raise ConnectionRefusedError("Falha na autenticação")