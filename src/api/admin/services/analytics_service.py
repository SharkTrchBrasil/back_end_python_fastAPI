# analytics_service.py (ou similar)

from sqlalchemy import func, extract
from sqlalchemy.orm import Session
from datetime import datetime, timedelta

from src.core import models


def get_peak_hours_for_store(db, store_id: int):
    """
    Analisa o histórico de pedidos dos últimos 90 dias para determinar os
    horários de pico para almoço e janta.
    """
    try:
        # 1. Define o intervalo de datas para a análise
        end_date = datetime.utcnow()
        start_date = end_date - timedelta(days=90)

        # 2. Consulta para contar pedidos por hora do dia
        order_counts_by_hour = (
            db.query(
                extract("hour", models.Order.created_at).label("hour"),
                func.count(models.Order.id).label("order_count"),
            )
            .filter(
                models.Order.store_id == store_id,
                models.Order.created_at.between(start_date, end_date),
            )
            .group_by("hour")
            .all()
        )

        # Se não houver pedidos no período, retorna um padrão seguro
        if not order_counts_by_hour:
            return {
                "lunchPeakStart": "12:00", "lunchPeakEnd": "14:00",
                "dinnerPeakStart": "19:00", "dinnerPeakEnd": "21:00"
            }

        # 3. Processa os resultados para encontrar os picos
        hourly_data = {hour: count for hour, count in order_counts_by_hour}

        # Define as janelas de tempo para almoço (10h-15h) e janta (17h-23h)
        lunch_window = range(10, 16)
        dinner_window = range(17, 24)

        # Encontra a hora com mais pedidos em cada janela
        lunch_peak_hour = max(
            (hour for hour in lunch_window if hour in hourly_data),
            key=lambda hour: hourly_data.get(hour, 0),
            default=12  # Padrão caso não haja pedidos na janela
        )
        dinner_peak_hour = max(
            (hour for hour in dinner_window if hour in hourly_data),
            key=lambda hour: hourly_data.get(hour, 0),
            default=20 # Padrão caso não haja pedidos na janela
        )

        # 4. Define o intervalo do pico (ex: a hora de pico +/- 1 hora) e formata
        return {
            "lunchPeakStart": f"{lunch_peak_hour - 1:02d}:00",
            "lunchPeakEnd": f"{lunch_peak_hour + 1:02d}:00",
            "dinnerPeakStart": f"{dinner_peak_hour - 1:02d}:00",
            "dinnerPeakEnd": f"{dinner_peak_hour + 1:02d}:00",
        }

    except Exception as e:
        print(f"❌ Erro ao calcular horários de pico para loja {store_id}: {e}")
        # Retorna um padrão seguro em caso de qualquer falha
        return {
            "lunchPeakStart": "12:00", "lunchPeakEnd": "14:00",
            "dinnerPeakStart": "19:00", "dinnerPeakEnd": "21:00"
        }