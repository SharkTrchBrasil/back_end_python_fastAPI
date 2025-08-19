# routers/holidays.py

from fastapi import APIRouter, HTTPException
import httpx  # Uma biblioteca moderna para fazer requisições HTTP. Instale com: pip install httpx
from typing import List

from src.api.schemas.holiday import HolidayOut

router = APIRouter(
    prefix="/holidays",
    tags=["Holidays"]
)


@router.get("/{year}", response_model=List[HolidayOut])
async def get_national_holidays(year: int):
    """
    Busca os feriados nacionais para um determinado ano a partir da BrasilAPI.
    """
    # Usamos httpx para fazer a chamada assíncrona para a API externa
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(f"https://brasilapi.com.br/api/feriados/v1/{year}")

            # Se a API externa falhar, retornamos um erro
            response.raise_for_status()

            # A resposta é uma lista de feriados que validamos com nosso schema
            holidays_data = response.json()

            # Filtramos para pegar apenas feriados nacionais, se desejado
            national_holidays = [h for h in holidays_data if h.get("type") == "national"]

            return national_holidays

        except httpx.RequestError as exc:
            print(f"Erro ao acessar a API de feriados: {exc}")
            raise HTTPException(status_code=503, detail="Serviço de feriados indisponível.")
        except Exception as e:
            print(f"Erro inesperado ao processar feriados: {e}")
            raise HTTPException(status_code=500, detail="Erro ao processar dados dos feriados.")