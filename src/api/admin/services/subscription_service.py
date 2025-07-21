from datetime import datetime, timedelta
from sqlalchemy.orm import Session, joinedload

from src.core import models
from src.api.admin.schemas.subscription import StoreSubscriptionOut


class SubscriptionService:

    @staticmethod
    def get_subscription_details(db, store_id: int) -> tuple[dict, bool]:
        """
        Verifica a assinatura, monta o payload detalhado e retorna o payload
        junto com um booleano indicando se a loja pode operar.
        """
        subscription_db = db.query(models.StoreSubscription).options(
            joinedload(models.StoreSubscription.plan)
            .joinedload(models.SubscriptionPlan.features)
        ).filter(
            models.StoreSubscription.store_id == store_id
        ).order_by(models.StoreSubscription.current_period_end.desc()).first()

        # Caso não haja assinatura
        if not subscription_db:
            payload = {
                "plan_name": "Nenhum", "status": "expired",
                "expiry_date": None, "features": [],
                "warning_message": "Nenhuma assinatura encontrada para esta loja."
            }
            return payload, False

        # Validação com Pydantic
        validated_sub = StoreSubscriptionOut.model_validate(subscription_db)

        # Lógica de status dinâmico
        now = datetime.utcnow()
        expiry_date = validated_sub.current_period_end
        grace_period_end = expiry_date + timedelta(days=3)
        dynamic_status = "unknown"
        warning_message = None

        if now <= expiry_date:
            dynamic_status = "active"
            remaining_days = (expiry_date - now).days
            if remaining_days < 0:
                warning_message = "Sua assinatura vence hoje!"
            elif remaining_days <= 3:
                warning_message = f"Sua assinatura vence em {remaining_days + 1} dia(s)."

        elif now <= grace_period_end:
            dynamic_status = "grace_period"
            warning_message = "Sua assinatura venceu! Renove para não perder o acesso."
        else:
            dynamic_status = "expired"
            warning_message = "Assinatura expirada. Funcionalidades bloqueadas."

        # Construção do payload final
        payload = {
            "plan_name": validated_sub.plan.plan_name,
            "expiry_date": expiry_date.isoformat() + "Z",
            "features": [f.feature_key for f in validated_sub.plan.features if f.is_enabled],
            "status": dynamic_status,
            "warning_message": warning_message
        }

        is_operational = dynamic_status != "expired"
        return payload, is_operational