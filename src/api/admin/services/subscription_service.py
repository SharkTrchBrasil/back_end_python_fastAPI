# src/core/models/subscription_service.py
from datetime import timedelta, datetime

from sqlalchemy.orm import Session

from src.core import models


class SubscriptionService:
    @staticmethod
    def get_store_access_level(db: Session, store_id: int) -> dict:
        """Retorna o nível de acesso baseado na assinatura"""
        subscription = db.query(models.StoreSubscription).filter(
            models.StoreSubscription.store_id == store_id
        ).order_by(models.StoreSubscription.current_period_end.desc()).first()

        if not subscription:
            return {
                'blocked': True,
                'access_level': 'none',
                'message': 'Nenhuma assinatura encontrada'
            }

        now = datetime.utcnow()
        is_active = (
                subscription.status == 'active' and
                subscription.current_period_end >= now
        )

        if is_active:
            return {
                'blocked': False,
                'access_level': 'full',
                'message': 'Assinatura ativa'
            }

        # Lógica para grace period (período de carência)
        grace_period_end = subscription.current_period_end + timedelta(days=3)
        if now <= grace_period_end:
            return {
                'blocked': False,
                'access_level': 'limited',
                'message': 'Período de carência - algumas funcionalidades limitadas'
            }

        return {
            'blocked': True,
            'access_level': 'none',
            'message': 'Assinatura vencida. Renove seu plano.'
        }