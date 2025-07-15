from datetime import datetime, timedelta

from socketio import AsyncNamespace

from src.core import models
from .handlers.connection_handler import (
    handle_admin_connect,
    handle_admin_disconnect
)
from .handlers.order_handler import handle_update_order_status
from .handlers.store_handler import (
    handle_join_store_room,
    handle_leave_store_room,
    handle_update_store_settings,
    handle_set_consolidated_stores
)
from ..socketio.emitters import admin_emit_store_full_updated, admin_emit_orders_initial, admin_product_list_all, \
    admin_emit_tables_and_commands


class AdminNamespace(AsyncNamespace):
    def __init__(self, namespace=None):
        super().__init__(namespace)
        self.environ = {}

    async def on_connect(self, sid, environ):
        await handle_admin_connect(self, sid, environ)

    async def on_disconnect(self, sid):
        await handle_admin_disconnect(self, sid)

    async def on_update_order_status(self, sid, data):
        return await handle_update_order_status(self, sid, data)

    async def on_join_store_room(self, sid, data):
        await handle_join_store_room(self, sid, data)

    async def on_leave_store_room(self, sid, data):
        await handle_leave_store_room(self, sid, data)

    async def on_update_store_settings(self, sid, data):
        return await handle_update_store_settings(self, sid, data)

    async def on_set_consolidated_stores(self, sid, data):
        return await handle_set_consolidated_stores(self, sid, data)




    async def _check_store_subscription(self, db, store_id):
        """Verifica se a loja tem assinatura ativa com tratamento de grace period"""
        subscription = db.query(models.StoreSubscription).filter(
            models.StoreSubscription.store_id == store_id,
            models.StoreSubscription.status == 'active'
        ).order_by(models.StoreSubscription.current_period_end.desc()).first()

        if not subscription:
            raise ConnectionRefusedError("Nenhuma assinatura encontrada para esta loja")

        now = datetime.utcnow()




        # Verifica se está no período ativo ou no grace period (3 dias após expiração)
        if now > subscription.current_period_end + timedelta(days=3):
            raise ConnectionRefusedError("Assinatura vencida. Renove seu plano para continuar.")

        return subscription


    async def _check_and_notify_subscription(self, db, store_id, sid):
        """Verifica assinatura e envia notificações se necessário"""
        try:
            subscription = await self._check_store_subscription(db, store_id)
            now = datetime.utcnow()
            remaining_days = (subscription.current_period_end - now).days

            # Notificações proativas
            if remaining_days <= 3:
                message = (
                    f"Sua assinatura vencerá em {remaining_days} dias" if remaining_days > 0
                    else "Sua assinatura venceu hoje"
                )

                await self.emit('subscription_warning', {
                    'message': message,
                    'critical': remaining_days <= 1,
                    'expiration_date': subscription.current_period_end.isoformat(),
                    'remaining_days': remaining_days
                }, to=sid)

            return now <= subscription.current_period_end

        except ConnectionRefusedError as e:
            await self.emit('subscription_warning', {
                'message': str(e),
                'critical': True
            }, to=sid)
            return False


    async def _emit_initial_data(self, db, store_id, sid):
        """Emite dados iniciais com verificação de assinatura"""
        try:
            is_active = await self._check_and_notify_subscription(db, store_id, sid)

            if not is_active:
                await self.emit('store_blocked', {
                    'store_id': store_id,
                    'message': 'Loja bloqueada devido a assinatura vencida',
                    'can_operate': False
                }, to=sid)
                return False

            # Emite os dados apenas se a loja estiver ativa
            await admin_emit_store_full_updated(db, store_id, sid=sid)
            await admin_product_list_all(db, store_id, sid=sid)
            await admin_emit_orders_initial(db, store_id, sid=sid)
            await admin_emit_tables_and_commands(db, store_id, sid)

            return True

        except Exception as e:
            print(f"❌ Erro ao emitir dados iniciais: {str(e)}")
            return False

