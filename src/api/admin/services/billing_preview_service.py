# src/api/admin/services/billing_preview_service.py

from datetime import datetime, date, timezone
from decimal import Decimal
from typing import Optional, Dict, Any
from sqlalchemy import func
from sqlalchemy.orm import Session

from src.core import models
import logging

logger = logging.getLogger(__name__)


class BillingPreviewService:
    """
    Serviço para calcular e projetar o resumo de faturamento e custos
    do plano para o ciclo de cobrança atual de uma loja.

    ✅ VERSÃO BLINDADA - Retorna None apenas quando apropriado
    """

    @staticmethod
    def _calculate_fee(revenue: Decimal, plan: models.Plans) -> Decimal:
        """
        Calcula a taxa do sistema com base no faturamento e nas regras do plano.
        """
        if not plan:
            return Decimal('0.0')

        minimum_fee = Decimal(plan.minimum_fee) / 100
        revenue_percentage = plan.revenue_percentage
        percentage_fee = revenue * revenue_percentage
        calculated_fee = max(minimum_fee, percentage_fee)

        if plan.revenue_cap_fee:
            revenue_cap_fee = Decimal(plan.revenue_cap_fee) / 100
            if calculated_fee > revenue_cap_fee:
                return revenue_cap_fee

        return calculated_fee

    @staticmethod
    def get_billing_preview(db: Session, store: models.Store) -> Optional[Dict[str, Any]]:
        """
        ✅ CORRIGIDO: Retorna None apenas se não houver assinatura ALGUMA

        Para assinaturas canceladas/expiradas, retorna dados zerados com aviso.
        """

        # ✅ BUSCA QUALQUER ASSINATURA (incluindo canceladas)
        subscription = store.subscriptions[0] if store.subscriptions else None

        if not subscription or not subscription.plan:
            logger.info(f"[BillingPreview] Loja {store.id} sem assinatura ou plano")
            return None

        # ═══════════════════════════════════════════════════════════
        # 🔴 TRATAMENTO ESPECIAL PARA ASSINATURAS NÃO-ATIVAS
        # ═══════════════════════════════════════════════════════════

        if subscription.status not in ['active', 'trialing']:
            logger.info(f"[BillingPreview] Loja {store.id}: Status '{subscription.status}' - Retornando preview zerado")

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

        # ═══════════════════════════════════════════════════════════
        # 🟢 CÁLCULO NORMAL PARA ASSINATURAS ATIVAS/TRIAL
        # ═══════════════════════════════════════════════════════════

        now = datetime.now(timezone.utc)
        period_start = subscription.current_period_start
        period_end = subscription.current_period_end

        if not all([period_start, period_end]):
            logger.warning(f"[BillingPreview] Loja {store.id}: Datas de período inválidas")
            return None

        if period_start.tzinfo is None:
            period_start = period_start.replace(tzinfo=timezone.utc)
        if period_end.tzinfo is None:
            period_end = period_end.replace(tzinfo=timezone.utc)

        # ✅ BUSCA FATURAMENTO ATÉ AGORA
        query_result = db.query(
            func.sum(models.Order.total_price).label('total_revenue'),
            func.count(models.Order.id).label('total_orders')
        ).filter(
            models.Order.store_id == store.id,
            models.Order.order_status.in_(['finalized', 'delivered']),
            models.Order.created_at >= period_start,
            models.Order.created_at <= now
        ).first()

        revenue_so_far = query_result.total_revenue or Decimal('0.0')
        orders_so_far = query_result.total_orders or 0

        # ✅ CALCULA TAXA ATÉ AGORA
        from src.api.jobs.billing import calculate_platform_fee, calculate_months_active

        months_active = calculate_months_active(subscription, date.today())

        fee_details = calculate_platform_fee(
            Decimal(str(revenue_so_far)),
            subscription.plan,
            months_active
        )

        fee_so_far = float(fee_details['final_fee'])

        # ✅ PROJEÇÃO LINEAR
        days_in_cycle = (period_end - period_start).days
        days_passed = (now - period_start).days

        if days_passed > 0 and revenue_so_far > 0:
            daily_avg_revenue = revenue_so_far / Decimal(days_passed)
            projected_revenue = daily_avg_revenue * Decimal(days_in_cycle)

            projected_fee_details = calculate_platform_fee(
                Decimal(str(projected_revenue)),
                subscription.plan,
                months_active
            )
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