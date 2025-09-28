# Adicione esta função no início do seu arquivo src/api/jobs/billing.py

from decimal import Decimal
from src.core import models


def calculate_monthly_fee(monthly_revenue: Decimal, plan: models.Plans) -> Decimal:
    """
    Calcula a taxa de assinatura mensal com base no faturamento da loja e
    nas regras do plano dinâmico.

    Args:
        monthly_revenue (Decimal): O faturamento total da loja no mês (ex: 5500.50).
        plan (models.Plans): O objeto do plano de assinatura da loja, vindo do banco.

    Returns:
        Decimal: O valor final da mensalidade a ser cobrada, em Reais.
    """
    # Converte os valores do plano (que estão em centavos no DB) para Reais
    revenue_in_reais = monthly_revenue
    minimum_fee = Decimal(plan.minimum_fee) / 100
    percentage_tier_start = Decimal(plan.percentage_tier_start) / 100
    percentage_tier_end = Decimal(plan.percentage_tier_end) / 100
    revenue_cap_fee = Decimal(plan.revenue_cap_fee) / 100

    # Regra 1: Faturamento até R$ 1100,00
    if revenue_in_reais <= percentage_tier_start:
        return minimum_fee

    # Regra 2: Faturamento entre R$ 1100,01 e R$ 7000,00
    if percentage_tier_start < revenue_in_reais <= percentage_tier_end:
        calculated_fee = revenue_in_reais * plan.revenue_percentage
        return calculated_fee

    # Regra 3: Faturamento acima de R$ 7000,00
    if revenue_in_reais > percentage_tier_end:
        return revenue_cap_fee

    # Retorno de segurança
    return minimum_fee