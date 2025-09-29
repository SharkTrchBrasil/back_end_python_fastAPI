# Versão Final: src/api/routers/webhooks/subscription_webhook.py

from fastapi import APIRouter, Response, status, Form
from typing import Annotated

from src.api.admin.services.payment import get_notification
from src.core import models
from src.core.database import GetDBDep


router = APIRouter(tags=["Webhook"], prefix="/webhook")


@router.post("/subscriptions")  # Mantenha a rota ou mude para /billing
def post_billing_notification(db: GetDBDep, notification: Annotated[str, Form()]):
    """
    Recebe e processa notificações da Efí sobre o status das cobranças.
    """
    try:
        events = get_notification(notification)

        # A notificação pode conter vários eventos, pegamos o último de cobrança
        last_charge_event = max(
            (event for event in events if event.get('type') == 'charge'),
            key=lambda e: e.get('id', 0),
            default=None
        )

        if not last_charge_event:
            return Response(status_code=status.HTTP_200_OK)

        charge_id = last_charge_event.get('identifiers', {}).get('charge_id')
        new_status = last_charge_event.get('status', {}).get('current')

        db_charge = db.query(models.MonthlyCharge).filter_by(
            gateway_transaction_id=str(charge_id)
        ).first()

        if not db_charge or not db_charge.subscription:  # Garante que a cobrança tem uma assinatura
            return Response(status_code=status.HTTP_200_OK)

        if new_status == 'paid':
            db_charge.status = "paid"
            # Se o pagamento foi bem-sucedido, garante que a assinatura está ativa
            if db_charge.subscription.status == 'past_due':
                db_charge.subscription.status = "active"
            print(f"✅ Cobrança ID {db_charge.id} (Loja {db_charge.store_id}) marcada como paga.")

        # ✅ LÓGICA PRINCIPAL AQUI
        elif new_status in ['canceled', 'failed']:
            db_charge.status = "failed"
            # Atualiza a assinatura principal para indicar que há um problema de pagamento
            db_charge.subscription.status = "past_due"
            print(
                f"❌ Cobrança ID {db_charge.id} (Loja {db_charge.store_id}) marcada como falha. Assinatura marcada como 'past_due'.")

        db.commit()

    except Exception as e:
        db.rollback()
        # Em produção, adicione um log detalhado aqui
        return Response(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)

    return Response(status_code=status.HTTP_200_OK)