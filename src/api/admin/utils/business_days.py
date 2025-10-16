# Arquivo: src/api/admin/utils/business_days.py

"""
Utilitários para cálculo de dias úteis
=======================================
Considera finais de semana e feriados nacionais brasileiros.
"""

from datetime import date, timedelta
from typing import Set

# ✅ FERIADOS NACIONAIS FIXOS DO BRASIL
FIXED_HOLIDAYS = {
    (1, 1),  # Ano Novo
    (4, 21),  # Tiradentes
    (5, 1),  # Dia do Trabalho
    (9, 7),  # Independência
    (10, 12),  # Nossa Senhora Aparecida
    (11, 2),  # Finados
    (11, 15),  # Proclamação da República
    (12, 25),  # Natal
}


def get_brazilian_holidays(year: int) -> Set[date]:
    """
    Retorna set com feriados nacionais brasileiros do ano.

    Inclui:
    - Feriados fixos
    - Carnaval (47 dias antes da Páscoa)
    - Sexta-feira Santa (2 dias antes da Páscoa)
    - Corpus Christi (60 dias depois da Páscoa)

    Args:
        year: Ano para calcular os feriados

    Returns:
        Set de objetos date com os feriados
    """
    from dateutil.easter import easter

    holidays = set()

    # Adiciona feriados fixos
    for month, day in FIXED_HOLIDAYS:
        holidays.add(date(year, month, day))

    # Calcula feriados móveis baseados na Páscoa
    easter_date = easter(year)

    # Carnaval (47 dias antes da Páscoa)
    holidays.add(easter_date - timedelta(days=47))

    # Sexta-feira Santa
    holidays.add(easter_date - timedelta(days=2))

    # Corpus Christi
    holidays.add(easter_date + timedelta(days=60))

    return holidays


def is_business_day(check_date: date) -> bool:
    """
    Verifica se a data é um dia útil.

    Args:
        check_date: Data para verificar

    Returns:
        True se for dia útil, False caso contrário

    Examples:
        >>> is_business_day(date(2025, 1, 1))  # Ano Novo
        False
        >>> is_business_day(date(2025, 1, 2))  # Quinta-feira normal
        True
    """
    # Verifica se é final de semana (5=sábado, 6=domingo)
    if check_date.weekday() >= 5:
        return False

    # Verifica se é feriado
    holidays = get_brazilian_holidays(check_date.year)
    if check_date in holidays:
        return False

    return True


def is_first_business_day(today: date) -> bool:
    """
    Verifica se hoje é o primeiro dia útil do mês.

    Args:
        today: Data para verificar

    Returns:
        True se for o primeiro dia útil do mês

    Examples:
        >>> # Se dia 1 cai em sábado, primeiro dia útil é dia 3 (segunda)
        >>> is_first_business_day(date(2025, 2, 1))  # Sábado
        False
        >>> is_first_business_day(date(2025, 2, 3))  # Segunda
        True
    """
    try:
        # Busca o primeiro dia útil do mês
        first_day = date(today.year, today.month, 1)

        while not is_business_day(first_day):
            first_day += timedelta(days=1)

        return today == first_day

    except Exception as e:
        # Fallback: apenas dia 1
        print(f"⚠️ Erro ao verificar dia útil: {e}")
        return today.day == 1


def get_next_business_day(from_date: date) -> date:
    """
    Retorna o próximo dia útil a partir da data fornecida.

    Args:
        from_date: Data de referência

    Returns:
        Próximo dia útil

    Examples:
        >>> get_next_business_day(date(2025, 1, 1))  # Quarta (feriado)
        date(2025, 1, 2)  # Quinta
    """
    next_day = from_date + timedelta(days=1)

    while not is_business_day(next_day):
        next_day += timedelta(days=1)

    return next_day


def get_business_days_in_month(year: int, month: int) -> int:
    """
    Conta quantos dias úteis há no mês.

    Args:
        year: Ano
        month: Mês (1-12)

    Returns:
        Número de dias úteis

    Examples:
        >>> get_business_days_in_month(2025, 1)
        23
    """
    from calendar import monthrange

    _, last_day = monthrange(year, month)
    count = 0

    for day in range(1, last_day + 1):
        if is_business_day(date(year, month, day)):
            count += 1

    return count