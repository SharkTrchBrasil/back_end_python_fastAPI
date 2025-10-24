# src/api/admin/services/billing_preview_service.py

from datetime import datetime, date, timezone
from decimal import Decimal
from typing import Optional, Dict, Any
from sqlalchemy import func
from sqlalchemy.orm import Session

from src.core import models
import logging

# --- ✅ 1. IMPORTAR O ENUM DE STATUS DO PEDIDO ---
from src.core.utils.enums import OrderStatus

logger = logging.getLogger(__name__)


class BillingPreviewService:
    """
    Serviço para calcular e projetar o resumo de faturamento e custos
    do plano para o ciclo de cobrança atual de uma loja.
    """

    @staticmethod
    def _calculate_fee(revenue: Decimal, plan: models.Plans) -> Decimal:
        # (Lógica mantida como está)
        if not plan:
            return Decimal('0.0')
        # ...
        return Decimal('0.0')

    @staticmethod
    def get_billing_preview(db: Session, store: models.Store) -> Optional[Dict[str, Any]]:
        """
        Calcula a prévia da fatura para a loja no período de faturamento atual.
        """
        subscription = store.latest_subscription
        if not subscription or not subscription.plan:
            logger.info(f"[BillingPreview] Loja {store.id} sem assinatura ou plano.")
            return None

        if subscription.status not in ['active', 'trialing']:
            logger.info(f"[BillingPreview] Loja {store.id}: Status '{subscription.status}' - Retornando preview zerado.")
            return {
                "period_start": subscription.current_period_start.isoformat(),
                "period_end": subscription.current_period_end.isoformat(),
                "revenue_so_far": 0.0,
                "orders_so_far": 0,
                "fee_so_far": 0.0,
                "projected_revenue": 0.0,
                "projected_fee": 0.0,
                "status_note": f"Assinatura {subscription.status}. Preview não disponível."
            }

        now = datetime.now(timezone.utc)
        period_start = subscription.current_period_start
        period_end = subscription.current_period_end

        if not all([period_start, period_end]):
            logger.warning(f"[BillingPreview] Loja {store.id}: Datas de período inválidas na assinatura.")
            return None

        if period_start.tzinfo is None: period_start = period_start.replace(tzinfo=timezone.utc)
        if period_end.tzinfo is None: period_end = period_end.replace(tzinfo=timezone.utc)

        # --- ✅ 2. CORREÇÃO DEFINITIVA APLICADA AQUI ---
        # Define a lista de status que são considerados para faturamento usando os
        # próprios membros do Enum. O SQLAlchemy se encarrega de extrair o valor correto ('finalized', 'delivered').
        billable_statuses = [
            OrderStatus.FINALIZED,
            OrderStatus.DELIVERED,
        ]

        # Busca faturamento até agora usando a lista de Enums.
        query_result = db.query(
            func.sum(models.Order.total_price).label('total_revenue'),
            func.count(models.Order.id).label('total_orders')
        ).filter(
            models.Order.store_id == store.id,
            models.Order.order_status.in_(billable_statuses), # <-- A MUDANÇA ESTÁ AQUI
            models.Order.created_at >= period_start,
            models.Order.created_at <= now
        ).first()

        revenue_so_far_cents = query_result.total_revenue or 0
        revenue_so_far = Decimal(revenue_so_far_cents) / 100
        orders_so_far = query_result.total_orders or 0

        from src.api.jobs.billing import calculate_platform_fee, calculate_months_active

        months_active = calculate_months_active(subscription, date.today())
        fee_details = calculate_platform_fee(revenue_so_far, subscription.plan, months_active)
        fee_so_far = float(fee_details['final_fee'])

        days_in_cycle = (period_end - period_start).days
        days_passed = (now - period_start).days if now > period_start else 0

        if days_passed > 0 and revenue_so_far > 0:
            daily_avg_revenue = revenue_so_far / Decimal(days_passed)
            projected_revenue = daily_avg_revenue * Decimal(days_in_cycle)
            projected_fee_details = calculate_platform_fee(projected_revenue, subscription.plan, months_active)
            projected_fee = float(projected_fee_details['final_fee'])
        else:
            projected_revenue = revenue_so_far
            projected_fee = fee_so_far

        return {
            "period_start": period_start.isoformat(),
            "period_end": period_end.isoformat(),
            "revenue_so_far": float(revenue_so_far),
            "orders_so_far": orders_so_far,
            "fee_so_far": fee_so_far,
            "projected_revenue": float(projected_revenue),
            "projected_fee": projected_fee,
        }