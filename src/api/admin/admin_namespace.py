from urllib.parse import parse_qs
from socketio import AsyncNamespace

from src.api.admin.schemas.store_settings import StoreSettingsBase
from src.api.app.events.socketio_emitters import emit_store_updated
from src.core import models  # Importe models para acessar TotemAuthorization
from src.api.admin.events.admin_socketio_emitters import (

    admin_emit_orders_initial, admin_product_list_all, admin_emit_store_full_updated, admin_emit_order_updated_from_obj,
    admin_emit_store_updated)
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
                totem = await authorize_admin(db, token)
                if not totem or not totem.store:
                    raise ConnectionRefusedError("Acesso negado")

                await update_sid(db, totem, sid)

                for store in totem.stores:
                    room = f"admin_store_{store.id}"
                    await self.enter_room(sid, room)
                    print(f"✅ Admin entrou na room: {room}")
                    await self._emit_initial_data(db, store.id, sid)

                db.commit()

            except Exception as e:
                db.rollback()
                print(f"❌ Erro na conexão: {str(e)}")
                raise

    async def on_disconnect(self, sid):
        print(f"[ADMIN] Desconexão: {sid}")
        with get_db_manager() as db:
            try:
                totem = db.query(models.TotemAuthorization).filter_by(sid=sid).first()
                if totem:
                    await self.leave_room(sid, f"admin_store_{totem.store_id}")
                    totem.sid = None
                    db.commit()
                    print(f"✅ Admin removido da room: admin_store_{totem.store_id}")
            except Exception as e:
                print(f"❌ Erro na desconexão: {str(e)}")
                db.rollback()

    async def _emit_initial_data(self, db, store_id, sid):
        await admin_emit_store_full_updated(db, store_id, sid)
        await admin_product_list_all(db, store_id, sid)
        await admin_emit_orders_initial(db, store_id, sid)

    async def on_update_order_status(self, sid, data):
        with get_db_manager() as db:
            store = db.query(models.TotemAuthorization).filter_by(sid=sid).first()
            if not store:
                return {'error': 'Loja não autorizada'}

            order = db.query(models.Order).filter_by(
                id=data['order_id'],
                store_id=store.store_id
            ).first()

            if not order:
                return {'error': 'Pedido não encontrado'}

            order.order_status = data['new_status']
            db.commit()
            db.refresh(order)

            await admin_emit_order_updated_from_obj(order)
            print(f"✅ Pedido {order.id} atualizado para: {data['new_status']}")

            return {'success': True}

    async def on_update_store_settings(self, sid, data):

        with get_db_manager() as db:
            store = db.query(models.TotemAuthorization).filter_by(sid=sid).first()
            if not store:
                return {'error': 'Loja não autorizada'}

            settings = db.query(models.StoreSettings).filter_by(store_id=store.store_id).first()
            if not settings:
                return {"error": "Configurações não encontradas"}

            try:
                for field in [
                    "is_delivery_active", "is_takeout_active", "is_table_service_active",
                    "is_store_open", "auto_accept_orders", "auto_print_orders"
                ]:
                    if field in data:
                        setattr(settings, field, data[field])

                db.commit()
                db.refresh(settings)

                await admin_emit_store_updated(settings.store)
                await emit_store_updated(store)
                return StoreSettingsBase.model_validate(settings).model_dump(mode='json')

            except Exception as e:
                db.rollback()
                return {"error": str(e)}
