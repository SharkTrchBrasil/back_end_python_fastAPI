from typing import Annotated
from datetime import datetime, timedelta

from fastapi import APIRouter, Form, Response, status

from src.api.admin.services.subscription_service import downgrade_to_free_plan
from src.api.app.services import payment as payment_services
from src.core import models
from src.core.database import GetDBDep

router = APIRouter(tags=["Subscriptions"], prefix="/webhook")


# ✅ CORREÇÃO APLICADA AQUI:
# A rota agora é "/subscriptions", resultando na URL final "/webhook/subscriptions"
@router.post("/subscriptions")
def post_notification(
        db: GetDBDep,
        notification: Annotated[str, Form()]
):
    """
    Recebe, processa e atualiza o status de uma assinatura com base em
    notificações do gateway de pagamento.
    """
    try:
        # 1. Processa a notificação para obter a lista de eventos
        events = payment_services.get_notification(notification)

        # 2. Encontra o evento de assinatura mais recente na notificação
        last_subscription_event = max(
            (event for event in events if event.get('type') == 'subscription'),
            key=lambda e: e.get('id', 0),
            default=None
        )

        if not last_subscription_event:
            print("Webhook recebido, mas sem evento de assinatura relevante.")
            return Response(status_code=status.HTTP_200_OK)

        # 3. Extrai os dados importantes do evento
        gateway_subscription_id = last_subscription_event.get('identifiers', {}).get('subscription_id')
        new_status = last_subscription_event.get('status', {}).get('current')

        if not gateway_subscription_id or not new_status:
            print(f"Webhook com dados incompletos: {last_subscription_event}")
            return Response(status_code=status.HTTP_200_OK)

        # 4. Busca a assinatura no seu banco usando a coluna correta
        db_subscription = db.query(models.StoreSubscription).filter_by(
            gateway_subscription_id=str(gateway_subscription_id) # Garante que o tipo é string
        ).first()

        if not db_subscription:
            print(f"Assinatura com ID de gateway {gateway_subscription_id} não encontrada no banco.")
            return Response(status_code=status.HTTP_200_OK)

        # 5. Atualiza o status da assinatura
        db_subscription.status = new_status
        print(f"Assinatura {db_subscription.id} atualizada para o status: {new_status}")

        # 6. Lógica de Downgrade
        if new_status == 'canceled':

           downgrade_to_free_plan(db, db_subscription)

        db.commit()

    except Exception as e:
        db.rollback()
        print(f"❌ Erro crítico ao processar webhook: {e}")
        # Retorna 500 para indicar um erro interno, mas o gateway pode tentar reenviar.
        # Em produção, você pode querer manter 200 para evitar reenvios em loop.
        return Response(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)

    return Response(status_code=status.HTTP_200_OK)
