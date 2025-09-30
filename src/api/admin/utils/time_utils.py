# src/core/time_utils.py
from datetime import datetime, timezone
from typing import Optional


def to_brazil_time(utc_dt: datetime) -> datetime:
    """
    Converte UTC para horário de São Paulo de forma segura.
    """
    if utc_dt.tzinfo is None:
        # Se não tem timezone, assume que é UTC
        utc_dt = utc_dt.replace(tzinfo=timezone.utc)

    # Converte para America/Sao_Paulo
    from datetime import timedelta
    return utc_dt.astimezone(timezone(timedelta(hours=-3)))


def format_brazil_datetime(utc_dt: datetime, format_str: str = "%d/%m/%Y %H:%M") -> str:
    """
    Formata datetime para string no horário de Brasil.
    """
    br_time = to_brazil_time(utc_dt)
    return br_time.strftime(format_str)


def now_utc() -> datetime:
    """
    Retorna o datetime atual em UTC.
    """
    return datetime.now(timezone.utc)


def now_brazil() -> datetime:
    """
    Retorna o datetime atual no horário de Brasil.
    """
    return to_brazil_time(now_utc())