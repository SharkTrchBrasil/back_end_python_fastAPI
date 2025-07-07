from urllib.parse import parse_qs
from socketio import AsyncNamespace
from src.core import models  # Importe models para acessar TotemAuthorization
from src.api.admin.events.admin_socketio_emitters import (
    emit_store_full_updated,
    product_list_all,
    emit_orders_initial, emit_order_updated_from_obj
)
from src.api.admin.services.authorize_admin import authorize_admin, update_sid
from src.core.database import get_db_manager


class AdminNamespace(AsyncNamespace):
    async def on_connect(self, sid, environ):
        print(f"[ADMIN] Conexão estabelecida: {sid}")
        query = parse_qs(environ.get('QUERY_STRING', ''))
        token = query.get('admin_token', [None])[0]

        if not token:
            raise ConnectionRefusedError("Token obrigatório")

        with get_db_manager() as db:
            try:
                # Autenticação
                totem = await authorize_admin(db, token)
                if not totem or not totem.store:
                    raise ConnectionRefusedError("Acesso negado")

                # Atualização do SID
                await update_sid(db, totem, sid)

                # Entrar na room específica
                room = f"admin_store_{totem.store.id}"
                await self.enter_room(sid, room)
                print(f"✅ Admin entrou na room: {room}")

                # Emitir dados iniciais
                await self._emit_initial_data(db, totem.store.id, sid)
                db.commit()

            except Exception as e:
                db.rollback()
                print(f"❌ Erro na conexão: {str(e)}")
                raise

    async def on_disconnect(self, sid):
        print(f"[ADMIN] Desconexão: {sid}")
        with get_db_manager() as db:
            try:
                # Limpeza ao desconectar
                totem = db.query(models.TotemAuthorization).filter_by(sid=sid).first()
                if totem:
                    # Sai da room e limpa o SID
                    await self.leave_room(sid, f"admin_store_{totem.store_id}")
                    totem.sid = None
                    db.commit()
                    print(f"✅ Admin removido da room: admin_store_{totem.store_id}")
            except Exception as e:
                print(f"❌ Erro na desconexão: {str(e)}")
                db.rollback()

    async def _emit_initial_data(self, db, store_id, sid):
        """Método interno para emissão agrupada"""
        await emit_store_full_updated(db, store_id, sid)
        await product_list_all(db, store_id, sid)
        await emit_orders_initial(db, store_id, sid)

    async def on_update_order_status(self, sid, data):  # <<<<< método dentro da classe
        with get_db_manager() as db:
            store = db.query(models.TotemAuthorization).filter(
                models.TotemAuthorization.sid == sid
            ).first()

            if not store:
                return {'error': 'Loja não autorizada'}

            order = db.query(models.Order).filter(
                models.Order.id == data['order_id'],
                models.Order.store_id == store.store_id
            ).first()

            if not order:
                return {'error': 'Pedido não encontrado'}

            order.order_status = data['new_status']
            db.commit()

            # ✅ Recarrega os dados atualizados do banco
            db.refresh(order)

            await emit_order_updated_from_obj(order)

            print(f"✅ Pedido {order.id} atualizado para: {data['new_status']}")

            return {'success': True}

