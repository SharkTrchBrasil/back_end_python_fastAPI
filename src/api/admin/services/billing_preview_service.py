# src/api/admin/services/billing_preview_service.py

from datetime import datetime, timezone
from decimal import Decimal
from sqlalchemy.orm import Session
from sqlalchemy import func, and_

from src.core import models  # Seus modelos SQLAlchemy/ORM


class BillingPreviewService:
    """
    Serviço para calcular e projetar o resumo de faturamento e custos
    do plano para o ciclo de cobrança atual de uma loja.
    """

    @staticmethod
    def _calculate_fee(revenue: Decimal, plan: models.Plans) -> Decimal:
        """
        Calcula a taxa do sistema com base no faturamento e nas regras do plano.
        Esta lógica deve espelhar sua cobrança real para garantir consistência.
        """
        if not plan:
            return Decimal('0.0')

        # Converte de centavos para Decimal para os cálculos
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
    def get_billing_preview(db: Session, store: models.Store) -> dict:
        """
        Gera o resumo de faturamento atual e projetado para o ciclo corrente.
        Retorna um dicionário pronto para ser serializado em JSON.
        """
        subscription = store.active_subscription
        if not subscription or not subscription.plan:
            return {"error": "Assinatura ou plano não encontrado."}

        now = datetime.now(timezone.utc)
        period_start = subscription.current_period_start
        period_end = subscription.current_period_end

        if not all([period_start, period_end]):
            return {"error": "Datas do ciclo de faturamento inválidas."}

        if period_start.tzinfo is None: period_start = period_start.replace(tzinfo=timezone.utc)
        if period_end.tzinfo is None: period_end = period_end.replace(tzinfo=timezone.utc)

        # 1. Buscar dados de faturamento e pedidos ATÉ A DATA ATUAL
        # Filtra apenas por pedidos que representam receita confirmada.
        query_result = db.query(
            # ✅ CORREÇÃO: models.Order.total_amount -> models.Order.total_price
            func.sum(models.Order.total_price).label('total_revenue'),
            func.count(models.Order.id).label('total_orders')
        ).filter(
            models.Order.store_id == store.id,
            models.Order.status.in_(['COMPLETED', 'DELIVERED', 'READY']),  # Status que contam como receita
            and_(
                models.Order.created_at >= period_start,
                models.Order.created_at <= now
            )
        ).first()

        revenue_so_far = query_result.total_revenue or Decimal('0.0')
        orders_so_far = query_result.total_orders or 0

        # 2. Calcular a taxa do sistema aplicada até agora
        fee_so_far = BillingPreviewService._calculate_fee(revenue_so_far, subscription.plan)

        # 3. Fazer a projeção linear para o final do mês
        days_in_cycle = (period_end - period_start).days
        days_passed = (now - period_start).days

        # Evita divisão por zero e projeções sem dados
        if days_passed > 0 and revenue_so_far > 0:
            daily_avg_revenue = revenue_so_far / Decimal(days_passed)
            projected_revenue = daily_avg_revenue * Decimal(days_in_cycle)
            projected_fee = BillingPreviewService._calculate_fee(projected_revenue, subscription.plan)
        else:
            # Se não há dados ou é o primeiro dia, a projeção é igual ao valor atual
            projected_revenue = revenue_so_far
            projected_fee = fee_so_far

        return {
            "period_start": period_start.isoformat(),
            "period_end": period_end.isoformat(),
            "revenue_so_far": float(revenue_so_far),
            "orders_so_far": orders_so_far,
            "fee_so_far": float(fee_so_far),
            "projected_revenue": float(projected_revenue),
            "projected_fee": float(projected_fee)
        }