# Arquivo: src/api/admin/utils/proration.py

import calendar
from datetime import date, datetime, timezone
from decimal import Decimal
from dateutil.relativedelta import relativedelta

from src.core import models


def calculate_prorated_charge(plan: models.Plans) -> dict:
    """
    Calcula o valor proporcional da taxa para ativação no meio do mês.

    Regras:
    - Se o plano tem first_month_free: retorna R$ 0
    - Caso contrário: calcula proporcionalmente aos dias restantes

    Returns:
        dict com:
            - amount_in_cents: Valor em centavos
            - description: Descrição da cobrança
            - new_period_end_date: Fim do período atual
            - period_start: Início do período (hoje)
            - period_end: Fim do período
    """
    today = datetime.now(timezone.utc)
    today_date = today.date()

    # ═══════════════════════════════════════════════════════════
    # CENÁRIO 1: PRIMEIRO MÊS GRÁTIS
    # ═══════════════════════════════════════════════════════════

    if plan.first_month_free:
        # Próximo período começa no primeiro dia do próximo mês
        next_month_start = (today + relativedelta(months=1)).replace(day=1)
        next_month_end = next_month_start + relativedelta(months=1) - relativedelta(days=1)

        return {
            "amount_in_cents": 0,
            "description": "🎁 Primeiro mês por nossa conta!",
            "new_period_end_date": next_month_end,
            "period_start": today,
            "period_end": next_month_end
        }

    # ═══════════════════════════════════════════════════════════
    # CENÁRIO 2: COBRANÇA PROPORCIONAL
    # ═══════════════════════════════════════════════════════════

    # Calcula dias no mês
    _, total_days_in_month = calendar.monthrange(today_date.year, today_date.month)

    # Dias restantes (incluindo hoje)
    remaining_days = total_days_in_month - today_date.day + 1

    # Se ativar no último dia do mês
    if remaining_days <= 0:
        next_month_start = (today + relativedelta(months=1)).replace(day=1)
        next_month_end = next_month_start + relativedelta(months=1) - relativedelta(days=1)

        return {
            "amount_in_cents": 0,
            "description": "Ativação no final do mês",
            "new_period_end_date": next_month_end,
            "period_start": today,
            "period_end": next_month_end
        }

    # Calcula valor proporcional
    minimum_fee_cents = plan.minimum_fee
    prorated_fee = (Decimal(minimum_fee_cents) / total_days_in_month) * remaining_days
    prorated_fee_cents = int(prorated_fee)

    # Último dia do mês atual
    last_day_of_month = date(today_date.year, today_date.month, total_days_in_month)

    description = f"Assinatura Proporcional - {remaining_days} dias de {today_date.strftime('%B')}"

    return {
        "amount_in_cents": prorated_fee_cents,
        "description": description,
        "new_period_end_date": last_day_of_month,
        "period_start": today,  # ✅ ADICIONADO
        "period_end": datetime.combine(last_day_of_month, datetime.max.time()).replace(tzinfo=timezone.utc)
        # ✅ ADICIONADO
    }