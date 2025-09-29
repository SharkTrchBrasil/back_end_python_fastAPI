# Versão Final: src/api/admin/services/subscription_service.py

from datetime import datetime, timedelta
from src.core import models


class SubscriptionService:
    @staticmethod
    def get_subscription_details(store: models.Store) -> tuple[dict, bool]:
        """
        Retorna os detalhes completos e o status dinâmico da assinatura
        para exibição e controle de acesso no frontend.
        """
        subscription_db = store.active_subscription

        # --- Cenário 1: Nenhuma assinatura encontrada ---
        if not subscription_db or not subscription_db.plan:
            payload = {
                "plan_name": "Nenhum",
                "status": "inactive",
                "is_blocked": True,
                "warning_message": "Nenhum plano ativo. Por favor, realize uma assinatura para ter acesso."
            }
            return payload, True  # is_blocked = True

        plan = subscription_db.plan
        now = datetime.utcnow()
        is_blocked = False
        warning_message = None

        # --- Cenário 2: Pagamento Pendente ---
        if subscription_db.status == 'past_due':
            dynamic_status = "past_due"
            is_blocked = True
            warning_message = "Houve uma falha no pagamento. Atualize seus dados para reativar o acesso."

        # --- Cenário 3: Assinatura Expirada (após período de carência) ---
        else:
            grace_period_end = subscription_db.current_period_end + timedelta(days=3)
            if now > grace_period_end:
                dynamic_status = "expired"
                is_blocked = True
                warning_message = "Sua assinatura expirou. Renove seu plano para continuar."
            else:
                # --- Cenário 4: Período de Aviso de Vencimento ---
                remaining_days = (subscription_db.current_period_end - now).days
                if remaining_days <= 3:
                    dynamic_status = "warning"
                    warning_message = f"Sua assinatura vencerá em {remaining_days + 1} dia(s)."
                else:
                    # --- Cenário 5: Assinatura Ativa ---
                    dynamic_status = "active"

        # --- Montagem do Payload Final ---
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