from datetime import datetime, timedelta
from src.core import models

class SubscriptionService:
    @staticmethod
    def get_subscription_details(store: models.Store) -> tuple[dict, bool]:
        # Acessa a assinatura ativa diretamente do objeto 'store' fornecido.
        subscription_db = store.active_subscription

        # ✅ CORREÇÃO: Todo o bloco de código abaixo foi indentado
        # para pertencer a este método.
        if not subscription_db:
            payload = {
                "plan_name": "Nenhum",
                "status": "expired",
                "expiry_date": None,
                "features": [],
                "warning_message": "Nenhuma assinatura encontrada para esta loja."
            }
            return payload, False

        # Lógica para unificar features do plano base e dos add-ons
        plan_features = {
            assoc.feature.feature_key
            for assoc in subscription_db.plan.included_features
        }
        addon_features = {
            addon.feature.feature_key
            for addon in subscription_db.subscribed_addons
        }
        all_features = sorted(list(plan_features.union(addon_features)))

        # Lógica de status dinâmico (grace period, etc.)
        now = datetime.utcnow()
        expiry_date = subscription_db.current_period_end
        grace_period_end = expiry_date + timedelta(days=3)
        dynamic_status = "unknown"
        warning_message = None

        if now <= expiry_date:
            dynamic_status = "active"
            # ... (sua lógica de aviso de vencimento)
        elif now <= grace_period_end:
            dynamic_status = "grace_period"
            warning_message = "Sua assinatura venceu! Renove para não perder o acesso."
        else:
            dynamic_status = "expired"
            warning_message = "Assinatura expirada. Funcionalidades bloqueadas."


        payload = {
            "plan_id": subscription_db.plan.id,  # 👈 novo campo
            "plan_name": subscription_db.plan.plan_name,
            "expiry_date": expiry_date.isoformat() + "Z",
            "features": all_features,
            "status": dynamic_status,
            "warning_message": warning_message
        }

        is_operational = dynamic_status != "expired"
        return payload, is_operational