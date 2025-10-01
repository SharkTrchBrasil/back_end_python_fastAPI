import httpx
from datetime import datetime, timedelta, timezone
from cachetools import cached, TTLCache
from src.api.schemas.analytics.dashboard import DashboardInsight, HolidayInsightDetails

# ✅ Cache para guardar os feriados por 24 horas. Essencial para performance!
holiday_cache = TTLCache(maxsize=10, ttl=86400)


class HolidayService:
    BRASIL_API_URL = "https://brasilapi.com.br/api/feriados/v1"

    @staticmethod
    @cached(holiday_cache)
    async def _fetch_holidays_for_year(year: int) -> list:
        """Busca (e armazena em cache) os feriados para um determinado ano."""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(f"{HolidayService.BRASIL_API_URL}/{year}")
                response.raise_for_status()
                return response.json()
        except httpx.HTTPStatusError as e:
            print(f"Erro ao buscar feriados da BrasilAPI: {e}")
            return []

    @staticmethod
    async def get_upcoming_holiday_insight(days_ahead: int = 10) -> DashboardInsight | None:
        """
        Verifica se há um feriado nacional nos próximos 'days_ahead' dias
        e retorna um objeto de insight se houver.
        """
        today = datetime.now(timezone.utc).date()
        current_year = today.year
        limit_date = today + timedelta(days=days_ahead)

        holidays = await HolidayService._fetch_holidays_for_year(current_year)

        for holiday_data in holidays:
            holiday_date = datetime.strptime(holiday_data["date"], "%Y-%m-%d").date()

            # Verifica se o feriado está no futuro e dentro da nossa janela de 10 dias
            if today < holiday_date <= limit_date:
                holiday_name = holiday_data["name"]

                # Monta a mensagem para o frontend
                day_of_week = holiday_date.strftime("%A").replace("-feira", "")  # ex: "Sábado"

                details = HolidayInsightDetails(
                    holiday_name=holiday_name,
                    holiday_date=holiday_date
                )

                return DashboardInsight(
                    insight_type="UPCOMING_HOLIDAY",
                    title=f"🎉 Feriado à Vista!",
                    message=f"{holiday_name} está chegando no próximo(a) {day_of_week}, {holiday_date.strftime('%d/%m')}.",
                    details=details
                )

        # Se o ano virar nos próximos 10 dias, verifica o próximo ano também
        if limit_date.year > current_year:
            next_year_holidays = await HolidayService._fetch_holidays_for_year(limit_date.year)
            # (Repetir a lógica de verificação para 'next_year_holidays')
            # ...

        return None