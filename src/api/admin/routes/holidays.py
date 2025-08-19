# routers/holidays.py

from fastapi import APIRouter, HTTPException
import httpx
from typing import List


# ✅ 1. IMPORTE O MÓDULO `date`
from datetime import date

from src.api.schemas.holiday import HolidayOut

router = APIRouter(
    prefix="/holidays",
    tags=["Holidays"]
)


@router.get("/{year}", response_model=List[HolidayOut])
async def get_national_holidays(year: int):
    """
    Busca os feriados nacionais para um determinado ano a partir da BrasilAPI,
    retornando apenas os feriados a partir da data atual.
    """
    # ✅ 2. PEGUE A DATA ATUAL
    hoje = date.today()

    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(f"https://brasilapi.com.br/api/feriados/v1/{year}")
            response.raise_for_status()
            holidays_data = response.json()

            national_holidays = [h for h in holidays_data if h.get("type") == "national"]

            # ✅ 3. FILTRE A LISTA DE FERIADOS
            # Converte a string de data de cada feriado para um objeto 'date'
            # e mantém na lista apenas aqueles cuja data é maior ou igual a hoje.
            upcoming_holidays = [
                h for h in national_holidays
                if date.fromisoformat(h.get("date", "1900-01-01")) >= hoje
            ]

            return upcoming_holidays

        except httpx.RequestError as exc:
            print(f"Erro ao acessar a API de feriados: {exc}")
            raise HTTPException(status_code=503, detail="Serviço de feriados indisponível.")
        except Exception as e:
            print(f"Erro inesperado ao processar feriados: {e}")
            raise HTTPException(status_code=500, detail="Erro ao processar dados dos feriados.")