from datetime import datetime, timedelta

from socketio import AsyncNamespace

from src.core import models
from .handlers.connection_handler import (
    handle_admin_connect,
    handle_admin_disconnect
)

from .handlers.order_handler import handle_update_order_status, claim_specific_print_job, handle_update_print_job_status
from .handlers.store_handler import (
    handle_join_store_room,
    handle_leave_store_room,

    handle_set_consolidated_stores, handle_update_operation_config
)


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
        return await handle_update_operation_config(self, sid, data)

    async def on_set_consolidated_stores(self, sid, data):
        return await handle_set_consolidated_stores(self, sid, data)

    # ✅ CORREÇÃO 2: Adiciona o método que recebe o evento do cliente
    async def on_claim_specific_print_job(self, sid, data):
        """
        Recebe o evento de reivindicação e chama a função de lógica,
        retornando seu resultado como o 'ack' para o cliente.
        """
        # O 'return' aqui é crucial para que a resposta seja enviada de volta.
        return await claim_specific_print_job(sid, data)

    # ✅ 2. Adiciona o novo método que recebe o evento do cliente
    async def on_update_print_job_status(self, sid, data):
        """
        Recebe a atualização de status do cliente (completed/failed) e
        chama a função de lógica, retornando o resultado.
        """
        return await handle_update_print_job_status(self, sid, data)



    async def _check_store_subscription(self, db, store_id: int) -> models.StoreSubscription:
        store = db.query(models.Store).filter(models.Store.id == store_id).first()
        if not store:
            raise ConnectionRefusedError("Loja não encontrada.")

        subscription = store.active_subscription
        if not subscription:
            raise ConnectionRefusedError("Nenhuma assinatura ativa encontrada para esta loja.")

        now = datetime.utcnow()
        grace_period_end = subscription.current_period_end + timedelta(days=3)

        if now > grace_period_end:
            subscription.status = 'expired'
            db.commit()
            raise ConnectionRefusedError("Assinatura vencida. Renove seu plano para continuar.")

        return subscription

    async def _check_and_notify_subscription(self, db, store_id: int, sid: str) -> bool:
        """
        Verifica a assinatura e envia avisos de vencimento. Agora usa a função refatorada.
        """
        try:
            subscription = await self._check_store_subscription(db, store_id)

            now = datetime.utcnow()
            remaining_days = (subscription.current_period_end - now).days

            if remaining_days <= 3 and remaining_days >= -3:
                if remaining_days >= 0:
                    message = f"Sua assinatura vencerá em {remaining_days + 1} dia(s)."
                else:
                    message = "Sua assinatura venceu! Renove para não perder o acesso."

                await self.emit('subscription_warning', {
                    'message': message,
                    'critical': remaining_days < 1,
                }, to=sid)

            return now <= subscription.current_period_end

        except ConnectionRefusedError as e:
            await self.emit('subscription_warning', {'message': str(e), 'critical': True}, to=sid)
            return False
