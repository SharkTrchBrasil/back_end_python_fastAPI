# Versão Final: src/api/admin/services/subscription_service.py

from src.core import models
from decimal import Decimal


class SubscriptionService:
    @staticmethod
    def get_subscription_details(store: models.Store) -> tuple[dict, bool]:
        """
        Retorna os detalhes do plano dinâmico para exibição no frontend.
        """
        subscription_db = store.active_subscription

        if not subscription_db or not subscription_db.plan:
            return {"plan_name": "Nenhum", "status": "inactive"}, False

        plan = subscription_db.plan
        dynamic_status = "active"  # Simplificado. Pode ser melhorado no futuro.

        plan_features = {f.feature.feature_key for f in plan.included_features}
        # Sua lógica de add-ons (se houver)
        # addon_features = {a.feature.feature_key for a in subscription_db.subscribed_addons}

        payload = {
            "plan_id": plan.id,
            "plan_name": plan.plan_name,
            "status": dynamic_status,
            "warning_message": None,
            "features": sorted(list(plan_features)),
            "pricing_rules": {
                "minimum_fee": plan.minimum_fee,
                "revenue_percentage": float(plan.revenue_percentage),
                "revenue_cap_fee": plan.revenue_cap_fee,
                "percentage_tier_start": plan.percentage_tier_start,
                "percentage_tier_end": plan.percentage_tier_end
            }
        }

        return payload, (dynamic_status == "active")

# Remova a função 'downgrade_to_free_plan' deste arquivo.