# src/api/admin/services/subscription_service.py

from datetime import datetime, timedelta, timezone

from src.api.schemas.subscriptions.plans import PlanSchema
from src.api.schemas.subscriptions.plans_addon import SubscribedAddonSchema
from src.core import models  # Supondo que seus modelos SQLAlchemy/ORM estejam aqui


class SubscriptionService:
    """
    Serviço responsável por consolidar e calcular o estado dinâmico
    da assinatura de uma loja para ser enviado ao frontend.
    """

    @staticmethod
    def get_subscription_details(store: models.Store) -> dict:
        """
        Retorna um dicionário único e inequívoco representando o estado da
        assinatura da loja. O frontend deve usar esses dados como fonte da verdade.

        Este método calcula um 'status dinâmico' e um booleano 'is_blocked'
        que o frontend deve consumir diretamente, sem recalcular.
        """
        subscription_db = store.active_subscription

        if not subscription_db or not subscription_db.plan:
            return {
                "plan": None,
                "status": "inactive",
                "is_blocked": True,
                "warning_message": "Nenhuma assinatura encontrada. Por favor, assine um plano para continuar.",
                "subscribed_addons": []
            }

        # --- Lógica de Cálculo de Status ---
        plan = subscription_db.plan
        now = datetime.now(timezone.utc)

        # Garante que a data do banco de dados seja "aware" (com fuso horário)
        end_date = subscription_db.current_period_end
        if end_date and end_date.tzinfo is None:
            end_date = end_date.replace(tzinfo=timezone.utc)

        # Inicializa os valores padrão
        dynamic_status = subscription_db.status
        is_blocked = False
        warning_message = None

        if subscription_db.status == 'trialing':
            remaining_days = (end_date - now).days if end_date else -1
            if remaining_days >= 0:
                # O +1 é para uma contagem mais amigável (ex: "termina em 1 dia" em vez de "0 dias")
                warning_message = f"Seu teste gratuito termina em {remaining_days + 1} dia(s)."
            else:
                # O trial acabou, mas o status ainda não foi atualizado pelo webhook/job
                dynamic_status = 'expired'
                is_blocked = True
                warning_message = "Seu período de teste terminou. Adicione um método de pagamento para continuar."

        elif subscription_db.status == 'past_due' or subscription_db.status == 'unpaid':
            dynamic_status = 'past_due'  # Unifica os status de falha de pagamento
            is_blocked = True
            warning_message = "Falha no pagamento. Atualize seus dados para reativar o acesso."

        elif subscription_db.status == 'canceled':
            dynamic_status = 'canceled'
            is_blocked = True
            warning_message = f"Sua assinatura foi cancelada. Ela permanecerá ativa até {end_date.strftime('%d/%m/%Y')}."

        elif subscription_db.status == 'active':
            # Lógica para assinaturas ativas que podem expirar ou entrar em warning
            grace_period_end = end_date + timedelta(days=3) if end_date else now

            if now > grace_period_end:
                dynamic_status = "expired"
                is_blocked = True
                warning_message = "Sua assinatura expirou. Renove para continuar o acesso."
            elif end_date and now > end_date:
                # Está dentro do período de carência
                dynamic_status = "past_due"
                is_blocked = True  # Bloqueia durante a carência até o pagamento ser confirmado
                warning_message = f"Seu pagamento está pendente. Regularize até {grace_period_end.strftime('%d/%m/%Y')} para evitar o cancelamento."
            elif end_date and (end_date - now).days <= 3:
                # Entrando no período de aviso
                remaining_days = (end_date - now).days
                dynamic_status = "warning"
                is_blocked = False  # Ainda não está bloqueado
                warning_message = f"Atenção: sua assinatura vence em {remaining_days + 1} dia(s)."
            else:
                # Tudo certo, assinatura ativa e longe de vencer.
                dynamic_status = "active"
                is_blocked = False

        else:  # Status desconhecido
            is_blocked = True
            warning_message = "O status da sua assinatura é desconhecido. Contate o suporte."

        # --- Montagem do Payload Final ---
        # Usando os schemas Pydantic para garantir a consistência do contrato da API
        plan_payload = PlanSchema.model_validate(plan).model_dump()
        addons_payload = [SubscribedAddonSchema.model_validate(addon).model_dump() for addon in
                          subscription_db.subscribed_addons]

        return {
            "plan": plan_payload,
            "status": dynamic_status,
            "is_blocked": is_blocked,
            "warning_message": warning_message,
            "subscribed_addons": addons_payload,
            # Mantendo os campos do schema StoreSubscription para consistência
            "id": subscription_db.id,
            "current_period_start": subscription_db.current_period_start,
            "current_period_end": subscription_db.current_period_end,
            "gateway_subscription_id": subscription_db.gateway_subscription_id,
        }