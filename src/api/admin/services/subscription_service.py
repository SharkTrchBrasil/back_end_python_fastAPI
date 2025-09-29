# Versão Final e Polida: src/api/admin/services/subscription_service.py

from datetime import datetime, timedelta, timezone
from src.core import models


class SubscriptionService:
    @staticmethod
    def get_subscription_details(store: models.Store) -> tuple[dict, bool]:
        """
        Retorna os detalhes completos e o status dinâmico da assinatura
        para exibição e controle de acesso no frontend.
        """
        subscription_db = store.active_subscription

        if not subscription_db or not subscription_db.plan:
            payload = {
                "plan_name": "Nenhum",
                "status": "inactive",
                "is_blocked": True,
                "warning_message": "Nenhum plano ativo. Por favor, realize uma assinatura para ter acesso."
            }
            return payload, True

        plan = subscription_db.plan
        # Garante que estamos sempre comparando com UTC para evitar erros de fuso horário
        now = datetime.now(timezone.utc)
        is_blocked = False
        warning_message = None

        # ✅ NOVO CENÁRIO: Tratamento explícito para o período de teste
        if subscription_db.status == 'trialing':
            dynamic_status = "trialing"
            is_blocked = False  # Durante o trial, o acesso nunca é bloqueado
            remaining_trial_days = (subscription_db.current_period_end - now).days

            if remaining_trial_days > 0:
                warning_message = f"Seu teste gratuito termina em {remaining_trial_days + 1} dia(s)."
            else:
                warning_message = "Seu período de teste terminou. Adicione um pagamento para ativar seu plano."

        elif subscription_db.status == 'past_due':
            dynamic_status = "past_due"
            is_blocked = True
            warning_message = "Houve uma falha no pagamento. Atualize seus dados para reativar o acesso."

        else:
            # Para status 'active' ou 'expired', a lógica de data decide o estado
            # Adicionamos um período de carência de 3 dias
            grace_period_end = subscription_db.current_period_end + timedelta(days=3)

            if now > grace_period_end:
                dynamic_status = "expired"
                is_blocked = True
                warning_message = "Sua assinatura expirou. Renove seu plano para continuar."
            else:
                remaining_days = (subscription_db.current_period_end - now).days
                if remaining_days <= 3:
                    dynamic_status = "warning"
                    warning_message = f"Sua assinatura vencerá em {remaining_days + 1} dia(s)."
                else:
                    dynamic_status = "active"

        # --- Montagem do Payload Final (sem alterações, já estava ótimo) ---
        plan_features = {f.feature.feature_key for f in plan.included_features}

        payload = {
            "plan_id": plan.id,
            "plan_name": plan.plan_name,
            "status": dynamic_status,
            "is_blocked": is_blocked,
            "warning_message": warning_message,
            "features": sorted(list(plan_features)),
            "pricing_rules": {
                "minimum_fee": plan.minimum_fee,
                "revenue_percentage": float(plan.revenue_percentage),
                "revenue_cap_fee": plan.revenue_cap_fee,
                "percentage_tier_start": plan.percentage_tier_start,
                "percentage_tier_end": plan.percentage_tier_end
            }
        }

        return payload, is_blocked