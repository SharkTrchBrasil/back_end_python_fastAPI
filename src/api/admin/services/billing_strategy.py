# src/api/admin/services/billing_strategy.py

"""
Estratégia de Cobrança Híbrida
===============================

REGRA:
- Lojas com faturamento < R$ 5.000/mês → Aniversário (distribui carga)
- Lojas com faturamento ≥ R$ 5.000/mês → Dia 1º (previsibilidade)

VANTAGENS:
- Pequenas lojas: Distribuição de carga no servidor
- Grandes lojas: Previsibilidade contábil
- Escalável: Modelo usado por Stripe, Shopify, HubSpot

EXEMPLO:
- Loja A (R$ 2.000/mês): Assina dia 15 → Cobra todo dia 15
- Loja B (R$ 8.000/mês): Assina dia 15 → Cobra todo dia 1º

Autor: Sistema de Billing
Última atualização: 2025-01-17
"""

from datetime import datetime, timezone, timedelta
from decimal import Decimal
from sqlalchemy.orm import Session
from sqlalchemy import func
import calendar
import logging

from src.core import models

logger = logging.getLogger(__name__)


class BillingStrategy:
    """Define quando cobrar cada loja baseado no perfil de faturamento"""

    # ✅ LIMITE PARA CONSIDERAR "GRANDE LOJA"
    ENTERPRISE_THRESHOLD = Decimal("5000.00")  # R$ 5.000,00

    @staticmethod
    def get_billing_date(
            subscription: models.StoreSubscription,
            db: Session
    ) -> datetime:
        """
        ✅ Retorna a próxima data de cobrança baseada no perfil da loja

        LÓGICA:
        1. Calcula faturamento médio dos últimos 3 meses
        2. Se < R$ 5k → Cobra no aniversário da assinatura
        3. Se ≥ R$ 5k → Cobra sempre dia 1º do mês

        Args:
            subscription: Assinatura da loja
            db: Sessão do banco de dados

        Returns:
            datetime: Próxima data de cobrança às 00:00 UTC
        """

        logger.info("─" * 60)
        logger.info(f"📊 [BillingStrategy] Calculando próxima cobrança")
        logger.info(f"   Store ID: {subscription.store_id}")

        # ═══════════════════════════════════════════════════════════
        # 1. CALCULA FATURAMENTO MÉDIO
        # ═══════════════════════════════════════════════════════════

        avg_revenue = BillingStrategy._get_average_revenue(
            db, subscription.store_id
        )

        logger.info(f"   Faturamento médio (3 meses): R$ {float(avg_revenue):.2f}")

        # ═══════════════════════════════════════════════════════════
        # 2. DECIDE ESTRATÉGIA
        # ═══════════════════════════════════════════════════════════

        if avg_revenue >= BillingStrategy.ENTERPRISE_THRESHOLD:
            # 🏢 GRANDE LOJA: Sempre dia 1º
            next_billing = BillingStrategy._get_next_first_day()
            strategy = "Dia 1º (Enterprise)"
        else:
            # 🏪 PEQUENA LOJA: Aniversário
            next_billing = BillingStrategy._get_next_anniversary(subscription)
            strategy = "Aniversário (Standard)"

        logger.info(f"   Estratégia: {strategy}")
        logger.info(f"   Próxima cobrança: {next_billing.date()}")
        logger.info("─" * 60)

        return next_billing

    @staticmethod
    def _get_average_revenue(db: Session, store_id: int) -> Decimal:
        """
        ✅ Calcula faturamento médio dos últimos 3 meses

        Considera apenas pedidos finalizados/entregues para
        evitar manipulação da estratégia.
        """

        three_months_ago = datetime.now(timezone.utc) - timedelta(days=90)

        result = db.query(
            func.sum(models.Order.total_price)
        ).filter(
            models.Order.store_id == store_id,
            models.Order.order_status.in_(['finalized', 'delivered']),
            models.Order.created_at >= three_months_ago
        ).scalar()

        if not result:
            return Decimal("0")

        # Converte centavos → reais e divide por 3 (média mensal)
        total_revenue = Decimal(result) / 100
        avg_monthly = total_revenue / 3

        return avg_monthly.quantize(Decimal('0.01'))

    @staticmethod
    def _get_next_first_day() -> datetime:
        """
        ✅ Retorna próximo dia 1º às 00:00 UTC

        REGRA:
        - Se hoje é dia 1-5: Cobra dia 1º DESTE mês
        - Se hoje é dia 6-31: Cobra dia 1º do PRÓXIMO mês

        Isso evita cobrar 2x no mesmo mês se a loja
        mudou de estratégia (cresceu de faturamento).
        """

        now = datetime.now(timezone.utc)

        # Se estamos antes do dia 5, cobra dia 1º DESTE mês
        if now.day <= 5:
            return datetime(
                now.year,
                now.month,
                1,
                0, 0, 0,
                tzinfo=timezone.utc
            )

        # Se estamos depois do dia 5, cobra dia 1º do PRÓXIMO mês
        if now.month == 12:
            next_year = now.year + 1
            next_month = 1
        else:
            next_year = now.year
            next_month = now.month + 1

        return datetime(
            next_year,
            next_month,
            1,
            0, 0, 0,
            tzinfo=timezone.utc
        )

    @staticmethod
    def _get_next_anniversary(
            subscription: models.StoreSubscription
    ) -> datetime:
        """
        ✅ Retorna próximo aniversário da assinatura

        REGRA:
        - Usa o DIA em que a assinatura foi criada
        - Cobra TODO MÊS no mesmo dia

        TRATAMENTO DE EXCEÇÕES:
        - Se criou dia 31, e o próximo mês tem apenas 30 dias,
          cobra no último dia do mês (ex: 30/04 ao invés de 31/04)

        Args:
            subscription: Assinatura da loja

        Returns:
            datetime: Próxima data de aniversário às 00:00 UTC
        """

        now = datetime.now(timezone.utc)
        start = subscription.current_period_start

        # ✅ Dia do mês que foi criada
        billing_day = start.day

        # ✅ Calcula próximo mês
        if now.month == 12:
            next_year = now.year + 1
            next_month = 1
        else:
            next_year = now.year
            next_month = now.month + 1

        # ✅ Ajusta se o dia não existe no próximo mês
        try:
            next_billing_date = datetime(
                next_year,
                next_month,
                billing_day,
                0, 0, 0,
                tzinfo=timezone.utc
            )
        except ValueError:
            # Dia não existe (ex: 31 de fevereiro)
            # Usa o último dia do mês
            last_day = calendar.monthrange(next_year, next_month)[1]
            next_billing_date = datetime(
                next_year,
                next_month,
                last_day,
                0, 0, 0,
                tzinfo=timezone.utc
            )

            logger.info(
                f"⚠️  Dia {billing_day} não existe em {next_month}/{next_year}. "
                f"Usando último dia ({last_day})"
            )

        return next_billing_date