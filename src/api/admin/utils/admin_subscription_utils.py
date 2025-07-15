from src.api.admin.services.subscription_service import SubscriptionService


async def check_and_notify_subscription(db, store_id, sid, socket):
    """Verifica a assinatura e envia um aviso via socket se necessário"""
    access = SubscriptionService.get_store_access_level(db, store_id)

    if access['blocked']:
        await socket.emit('subscription_warning', {
            'message': access['message'],
            'critical': True
        }, to=sid)
        return False

    if access['access_level'] == 'limited':
        await socket.emit('subscription_warning', {
            'message': access['message'],
            'critical': True,
        }, to=sid)

    return True
