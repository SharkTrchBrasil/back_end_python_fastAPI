# Arquivo: src/api/admin/utils/proration.py
import calendar
from datetime import date, timedelta
from decimal import Decimal

from src.core import models


def calculate_prorated_charge(plan: models.Plans) -> dict:
    """
    Calcula o valor proporcional da taxa mínima para os dias restantes no mês atual.
    """
    today = date.today()
    # Encontra o número de dias no mês atual
    _, total_days_in_month = calendar.monthrange(today.year, today.month)

    # Calcula os dias restantes, incluindo hoje
    remaining_days_in_month = total_days_in_month - today.day + 1

    # Garante que não haja cobrança indevida no último dia, se a lógica de negócio preferir
    if remaining_days_in_month <= 0:
        return {
            "amount_in_cents": 0,
            "description": "Ativação no final do mês",
            "new_period_end_date": today
        }

    minimum_fee_cents = plan.minimum_fee

    # Fórmula da cobrança proporcional
    prorated_fee = (Decimal(minimum_fee_cents) / total_days_in_month) * remaining_days_in_month
    prorated_fee_cents = int(prorated_fee)

    # Define o fim do período para o último dia do mês atual
    last_day_of_month = date(today.year, today.month, total_days_in_month)

    description = f"Assinatura Proporcional - {remaining_days_in_month} dias de {today.strftime('%B')}"

    return {
        "amount_in_cents": prorated_fee_cents,
        "description": description,
        "new_period_end_date": last_day_of_month
    }