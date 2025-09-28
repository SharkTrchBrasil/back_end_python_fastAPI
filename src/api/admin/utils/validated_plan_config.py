from decimal import Decimal

from src.core import models


def validate_plan_configuration(plan: models.Plans) -> list:
    """
    Valida se a configuração do plano dinâmico está correta.
    Retorna lista de erros. Lista vazia = plano válido.
    """
    errors = []

    # 1. Valida taxa mínima
    if plan.minimum_fee <= 0:
        errors.append("Taxa mínima deve ser maior que zero")
    elif plan.minimum_fee < 100:  # Menos de R$ 1,00?
        errors.append("Taxa mínima muito baixa (mínimo recomendado: R$ 1,00)")

    # 2. Valida porcentagem
    if not (0 < plan.revenue_percentage < 1):
        errors.append("Porcentagem de revenue deve estar entre 0 e 1 (ex: 3.6% = 0.036)")
    elif plan.revenue_percentage > Decimal('0.1'):  # Mais de 10%?
        errors.append("Porcentagem muito alta (máximo recomendado: 10%)")

    # 3. Valida faixas de faturamento
    if plan.percentage_tier_start >= plan.percentage_tier_end:
        errors.append("Início da faixa deve ser menor que o fim")
    elif plan.percentage_tier_start <= 0:
        errors.append("Início da faixa deve ser maior que zero")

    # 4. Valida teto de cobrança
    if plan.revenue_cap_fee:
        if plan.revenue_cap_fee < plan.minimum_fee:
            errors.append("Teto de cobrança não pode ser menor que a taxa mínima")
        elif plan.revenue_cap_fee > 1000000:  # Mais de R$ 10.000?
            errors.append("Teto de cobrança muito alto")

    # 5. Valida nomes e campos obrigatórios
    if not plan.plan_name or len(plan.plan_name.strip()) == 0:
        errors.append("Nome do plano é obrigatório")

    return errors