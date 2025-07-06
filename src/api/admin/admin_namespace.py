from urllib.parse import parse_qs

from socketio import AsyncNamespace

from src.api.admin.events.admin_socketio_emitters import emit_store_full_updated, product_list_all, emit_orders_initial
from src.api.admin.services.authorize_admin import authorize_admin, update_sid
from src.core.database import get_db_manager


class AdminNamespace(AsyncNamespace):
    async def on_connect(self, sid, environ):
        print(f"[ADMIN] Conexão: {sid}")
        query = parse_qs(environ.get('QUERY_STRING', ''))
        token = query.get('admin_token', [None])[0]

        if not token:
            raise ConnectionRefusedError("Token obrigatório")

        with get_db_manager() as db:
            try:
                totem = await authorize_admin(db, token)
                if not totem or not totem.store:
                    raise ConnectionRefusedError("Acesso negado")

                await update_sid(db, totem, sid)
                room = f"admin_store_{totem.store.id}"
                await self.enter_room(sid, room)

                # Emissão otimizada
                await self._emit_initial_data(db, totem.store.id, sid)

                db.commit()  # Confirma todas as operações

            except Exception as e:
                db.rollback()
                print(f"❌ Erro: {str(e)}")
                raise

    async def _emit_initial_data(self, db, store_id, sid):
        """Método interno para emissão agrupada"""
        await emit_store_full_updated(db, store_id, sid)
        await product_list_all(db, store_id, sid)
        await emit_orders_initial(db, store_id, sid)

