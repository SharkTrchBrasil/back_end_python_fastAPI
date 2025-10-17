# src/api/admin/utils/proration.py

"""
Cálculo de Cobrança Proporcional
=================================

✅ VERSÃO CORRIGIDA: Evita cobrança duplicada

ANTES (❌):
- Cliente assina dia 15/11
- Cobra proporcional até 30/11 (15 dias)
- Próxima cobrança: 15/12 ❌ DUPLICA!

DEPOIS (✅):
- Cliente assina dia 15/11
- Cobra valor completo (1º mês grátis se configurado)
- Período: 15/11 até 15/12 (30 dias)
- Próxima cobrança: 15/12 ✅ CORRETO!

Autor: Sistema de Billing
Última atualização: 2025-01-17
"""

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Dict
import logging

from src.core import models

logger = logging.getLogger(__name__)


def calculate_prorated_charge(plan: models.Plans) -> Dict:
    """
    ✅ CORRIGIDO: Calcula primeira cobrança com período de 30 dias

    REGRA DE NEGÓCIO:
    - Cliente paga pelo MÊS COMPLETO na assinatura
    - Se 1º mês grátis: amount = 0, mas período = 30 dias
    - Se não grátis: amount = taxa mínima, período = 30 dias

    Isso garante que o JOB mensal só cobre APÓS 30 dias,
    evitando duplicatas.

    Args:
        plan: Plano de assinatura

    Returns:
        Dict com:
        - amount_in_cents: Valor a cobrar (int)
        - period_start: Data de início do período (datetime)
        - period_end: Data de fim do período (datetime)
        - new_period_end_date: Próxima data de renovação (datetime)
        - description: Descrição da cobrança (str)
    """

    logger.info("═" * 60)
    logger.info("💰 [Proration] Calculando primeira cobrança")
    logger.info("═" * 60)

    now = datetime.now(timezone.utc)

    # ═══════════════════════════════════════════════════════════
    # ✅ CORREÇÃO CRÍTICA: Período de 30 DIAS (não até fim do mês)
    # ═══════════════════════════════════════════════════════════

    period_start = now
    period_end = now + timedelta(days=30)

    logger.info(f"📅 Período: {period_start.date()} até {period_end.date()}")
    logger.info(f"📊 Dias no ciclo: 30 dias")

    # ═══════════════════════════════════════════════════════════
    # ✅ BENEFÍCIO: 1º MÊS GRÁTIS
    # ═══════════════════════════════════════════════════════════

    if plan.first_month_free:
        amount_in_cents = 0
        description = "🎉 1º mês GRÁTIS - Bem-vindo ao MenuHub!"

        logger.info("🎁 1º mês GRÁTIS aplicado!")
        logger.info(f"💳 Valor a cobrar: R$ 0,00")

    else:
        # Cobra taxa mínima do plano
        amount_in_cents = plan.minimum_fee  # Ex: 3990 = R$ 39,90
        description = f"Primeira mensalidade - {now.strftime('%d/%m/%Y')}"

        logger.info(f"💳 Valor a cobrar: R$ {amount_in_cents / 100:.2f}")

    # ═══════════════════════════════════════════════════════════
    # ✅ RETORNO ESTRUTURADO
    # ═══════════════════════════════════════════════════════════

    result = {
        "amount_in_cents": amount_in_cents,
        "period_start": period_start,
        "period_end": period_end,
        "new_period_end_date": period_end,  # ← Próxima renovação
        "description": description
    }

    logger.info("─" * 60)
    logger.info("✅ Cálculo concluído:")
    logger.info(f"   Período: {period_start.date()} → {period_end.date()}")
    logger.info(f"   Valor: R$ {amount_in_cents / 100:.2f}")
    logger.info(f"   Próxima cobrança: {period_end.date()}")
    logger.info("═" * 60)

    return result