# src/api/admin/services/subscription_service.py

from datetime import datetime, timedelta, timezone
from src.api.schemas.subscriptions.plans import PlanSchema
from src.api.schemas.subscriptions.plans_addon import SubscribedAddonSchema
from src.core import models
import logging

logger = logging.getLogger(__name__)


class SubscriptionService:
    """
    Serviço responsável por consolidar e calcular o estado dinâmico
    da assinatura de uma loja para ser enviado ao frontend.
    """



    @staticmethod
    def get_subscription_details(store: models.Store) -> dict | None:
        """
        Retorna um dicionário representando o estado da assinatura.
        """
        subscription_db = store.active_subscription

        # ✅ CORREÇÃO: Se não tem assinatura, retorna None
        if not subscription_db or not subscription_db.plan:
            logger.info(f"[Subscription] Loja {store.id} não possui assinatura ativa.")
            return None

        # --- Lógica de Cálculo de Status ---
        plan = subscription_db.plan
        now = datetime.now(timezone.utc)

        end_date = subscription_db.current_period_end
        if end_date and end_date.tzinfo is None:
            end_date = end_date.replace(tzinfo=timezone.utc)

        dynamic_status = subscription_db.status
        is_blocked = False
        warning_message = None

        # ✅ CORREÇÃO: ADICIONAR TRATAMENTO PARA STATUS CANCELED
        if subscription_db.status == 'canceled':
            dynamic_status = 'canceled'
            is_blocked = True
            warning_message = f"Sua assinatura foi cancelada. Ela permanecerá ativa até {end_date.strftime('%d/%m/%Y')}." if end_date else "Sua assinatura foi cancelada."

        elif subscription_db.status == 'trialing':
            remaining_days = (end_date - now).days if end_date else -1
            if remaining_days >= 0:
                warning_message = f"Seu teste gratuito termina em {remaining_days + 1} dia(s)."
            else:
                dynamic_status = 'expired'
                is_blocked = True
                warning_message = "Seu período de teste terminou. Adicione um método de pagamento para continuar."

        elif subscription_db.status in ['past_due', 'unpaid']:
            dynamic_status = 'past_due'
            is_blocked = True
            warning_message = "Falha no pagamento. Atualize seus dados para reativar o acesso."

        elif subscription_db.status == 'active':
            grace_period_end = end_date + timedelta(days=3) if end_date else now

            if now > grace_period_end:
                dynamic_status = "expired"
                is_blocked = True
                warning_message = "Sua assinatura expirou. Renove para continuar o acesso."
            elif end_date and now > end_date:
                dynamic_status = "past_due"
                is_blocked = True
                warning_message = f"Seu pagamento está pendente. Regularize até {grace_period_end.strftime('%d/%m/%Y')} para evitar o cancelamento."
            elif end_date and (end_date - now).days <= 3:
                remaining_days = (end_date - now).days
                dynamic_status = "warning"
                is_blocked = False
                warning_message = f"Atenção: sua assinatura vence em {remaining_days + 1} dia(s)."
            else:
                dynamic_status = "active"
                is_blocked = False

        else:
            is_blocked = True
            warning_message = "O status da sua assinatura é desconhecido. Contate o suporte."

        # ✅ VERIFICA SE TEM MÉTODO DE PAGAMENTO
        has_payment_method = bool(
            store.pagarme_customer_id and
            store.pagarme_card_id
        )

        # ✅ LOG DETALHADO
        logger.info("═" * 60)
        logger.info(f"💳 [Subscription] Loja {store.id}:")
        logger.info(f"   - Status DB: {subscription_db.status}")
        logger.info(f"   - Status Calculado: {dynamic_status}")
        logger.info(f"   - Is Blocked: {is_blocked}")
        logger.info(f"   - Customer ID: {store.pagarme_customer_id}")
        logger.info(f"   - Card ID: {'✅ Presente' if store.pagarme_card_id else '❌ Ausente'}")
        logger.info(f"   - Has Payment Method: {has_payment_method}")
        logger.info("═" * 60)

        # ✅ RETORNA SEMPRE (mesmo se cancelada)
        return {
            "id": subscription_db.id,
            "current_period_start": subscription_db.current_period_start,
            "current_period_end": subscription_db.current_period_end,
            "gateway_subscription_id": subscription_db.gateway_subscription_id,
            "status": dynamic_status,
            "is_blocked": is_blocked,
            "warning_message": warning_message,
            "has_payment_method": has_payment_method,
            "plan": plan,
            "subscribed_addons": subscription_db.subscribed_addons,
        }