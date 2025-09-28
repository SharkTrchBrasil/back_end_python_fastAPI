from datetime import date, timedelta

from src.api.admin.routes import holidays


def is_first_business_day(today: date) -> bool:
    """
    Verifica se hoje é o primeiro dia útil do mês.
    Considera finais de semana e feriados nacionais do Brasil.
    """
    try:
        # Se não é dia 1, não é primeiro dia útil
        if today.day != 1:
            return False

        # Se dia 1 é sábado (5), domingo (6) ou feriado
        if today.weekday() >= 5 or today in holidays:
            return False

        return True

    except Exception as e:
        print(f"⚠️ Erro ao verificar dia útil: {e}")
        # Fallback: executa apenas no dia 1
        return today.day == 1


def get_next_business_day(today: date) -> date:
    """
    Retorna o próximo dia útil a partir de hoje.
    Útil para saber quando o job será executado.
    """
    next_day = today

    while next_day.weekday() >= 5 or next_day in holidays:
        next_day += timedelta(days=1)

    return next_day