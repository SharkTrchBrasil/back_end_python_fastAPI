from datetime import datetime
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

                # Criar/atualizar sessão na tabela store_sessions
                session = db.query(models.StoreSession).filter_by(sid=sid).first()
                if not session:
                    session = models.StoreSession(
                        sid=sid,
                        store_id=totem.store.id,
                        client_type='admin'
                    )
                    db.add(session)
                else:
                    session.store_id = totem.store.id
                    session.client_type = 'admin'
                    session.updated_at = datetime.utcnow()

                db.commit()
                print(f"✅ Session criada/atualizada para sid {sid}")

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
                # Remover a sessão ao desconectar
                session = db.query(models.StoreSession).filter_by(sid=sid).first()
                if session:
                    await self.leave_room(sid, f"admin_store_{session.store_id}")
                    db.delete(session)
                    db.commit()
                    print(f"✅ Session removida para sid {sid}")

                # Opcional: também limpar o sid do totem (se ainda estiver usando)
                totem = db.query(models.TotemAuthorization).filter_by(sid=sid).first()
                if totem:
                    totem.sid = None
                    db.commit()
            except Exception as e:
                print(f"❌ Erro na desconexão: {str(e)}")
                db.rollback()




    async def _emit_initial_data(self, db, store_id, sid):
        await admin_emit_store_full_updated(db, store_id, sid)
        await admin_product_list_all(db, store_id, sid)
        await admin_emit_orders_initial(db, store_id, sid)

    async def on_update_order_status(self, sid, data):
        with get_db_manager() as db:
            try:
                # 1. Validação básica dos dados de entrada
                if not all(key in data for key in ['order_id', 'new_status']):
                    return {'error': 'Dados incompletos'}

                # 2. Verifica a sessão (admin OU totem)
                session = db.query(models.StoreSession).filter_by(sid=sid).first()
                if not session:
                    return {'error': 'Sessão não autorizada'}

                # 3. Busca o pedido vinculado à LOJA da sessão
                order = db.query(models.Order).filter_by(
                    id=data['order_id'],
                    store_id=session.store_id
                ).first()

                if not order:
                    return {'error': 'Pedido não encontrado nesta loja'}

                # 4. Valida o novo status (exemplo com enum)
                valid_statuses = ['pending', 'preparing', 'ready', 'delivered']
                if data['new_status'] not in valid_statuses:
                    return {'error': 'Status inválido'}

                # 5. Atualização segura
                order.order_status = data['new_status']
                db.commit()
                db.refresh(order)

                # 6. Notificação
                await admin_emit_order_updated_from_obj(order)
                print(f"✅ [Session {sid}] Pedido {order.id} atualizado para: {data['new_status']}")

                return {'success': True, 'order_id': order.id, 'new_status': order.order_status}

            except Exception as e:
                db.rollback()
                print(f"❌ Erro ao atualizar pedido: {str(e)}")
                return {'error': 'Falha interna'}

    async def on_update_store_settings(self, sid, data):
        with get_db_manager() as db:
            # Agora verificamos a sessão em vez do totem diretamente
            session = db.query(models.StoreSession).filter_by(sid=sid, client_type='admin').first()
            if not session:
                return {'error': 'Sessão não encontrada ou não autorizada'}

            store = db.query(models.Store).filter_by(id=session.store_id).first()
            if not store:
                return {"error": "Loja associada não encontrada"}

            settings = db.query(models.StoreSettings).filter_by(store_id=store.id).first()
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
                db.refresh(store)

                await admin_emit_store_updated(store)
                await admin_emit_store_full_updated(db, store.id)

                return StoreSettingsBase.model_validate(settings).model_dump(mode='json')

            except Exception as e:
                db.rollback()
                print(f"❌ Erro ao atualizar configurações da loja: {str(e)}")
                return {"error": str(e)}


    async def on_join_store_room(self, sid, data):
        try:
            store_id = data.get("store_id")
            if not store_id:
                print("❌ store_id ausente em join_store_room")
                return

            room = f"admin_store_{store_id}"
            await self.enter_room(sid, room)
            print(f"✅ Admin entrou na sala dinâmica: {room}")
        except Exception as e:
            print(f"❌ Erro ao entrar na sala da loja {store_id}: {e}")

    async def on_leave_store_room(self, sid, data):
        try:
            store_id = data.get("store_id")
            if not store_id:
                print("❌ store_id ausente em leave_store_room")
                return

            room = f"admin_store_{store_id}"
            await self.leave_room(sid, room)
            print(f"🚪 Admin saiu da sala: {room}")
        except Exception as e:
            print(f"❌ Erro ao sair da sala da loja {store_id}: {e}")
