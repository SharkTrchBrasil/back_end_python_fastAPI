from typing import Annotated
from datetime import datetime, timedelta

from fastapi import APIRouter, Form, Response, status
from src.api.app.services import payment as payment_services
from src.core import models
from src.core.database import GetDBDep

router = APIRouter(tags=["Subscriptions"], prefix="/webhook")


@router.post("")
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

        # ✅ 4. Busca a assinatura no seu banco usando a coluna correta
        db_subscription = db.query(models.StoreSubscription).filter_by(
            gateway_subscription_id=gateway_subscription_id
        ).first()

        if not db_subscription:
            print(f"Assinatura com ID de gateway {gateway_subscription_id} não encontrada no banco.")
            return Response(status_code=status.HTTP_200_OK)

        # 5. Atualiza o status da assinatura
        db_subscription.status = new_status
        print(f"Assinatura {db_subscription.id} atualizada para o status: {new_status}")

        # ✅ 6. LÓGICA DE DOWNGRADE CORRIGIDA
        if new_status == 'canceled':
            # Busca o plano gratuito disponível
            free_plan = db.query(models.Plans).filter_by(price=0, available=True).first()

            if free_plan:
                print(f"Realizando downgrade da loja {db_subscription.store_id} para o plano gratuito.")
                # Modifica a assinatura EXISTENTE em vez de criar uma nova
                db_subscription.subscription_plan_id = free_plan.id
                db_subscription.gateway_subscription_id = None  # Limpa o ID do gateway antigo
                db_subscription.status = 'active'  # A assinatura agora está ativa no plano gratuito

                # Define um novo período de validade longo para o plano gratuito
                db_subscription.current_period_start = datetime.utcnow()
                db_subscription.current_period_end = datetime.utcnow() + timedelta(days=365 * 100)
            else:
                print("AVISO: Plano gratuito não encontrado para realizar o downgrade.")

        db.commit()

    except Exception as e:
        # Em caso de qualquer erro, desfaz as alterações e registra o problema
        db.rollback()
        print(f"❌ Erro crítico ao processar webhook: {e}")
        # Ainda retorna 200 para que o gateway não tente reenviar
        return Response(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)

    # 💡 Boa prática: Sempre retorne 200 OK para o gateway para confirmar o recebimento.
    return Response(status_code=status.HTTP_200_OK)