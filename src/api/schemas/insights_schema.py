from pydantic import BaseModel
from datetime import date
from typing import Literal, Union


# --- Schemas de Detalhes Específicos ---

class HolidayInsightDetails(BaseModel):
    holiday_name: str
    holiday_date: date


class LowStockInsightDetails(BaseModel):
    product_id: int
    product_name: str
    current_stock: int
    min_stock: int
    is_top_seller: bool  # Informação extra de alto valor!


class LowMoverInsightDetails(BaseModel):
    product_id: int
    product_name: str
    days_since_last_sale: int


# --- Schema Principal e Genérico ---

class DashboardInsight(BaseModel):
    # O tipo do insight, para o frontend saber como renderizar
    insight_type: Literal["UPCOMING_HOLIDAY", "LOW_STOCK", "LOW_MOVER_ITEM"]

    # Textos pré-formatados para facilitar a vida do frontend
    title: str
    message: str

    # O payload de dados específicos para cada tipo de insight
    details: Union[HolidayInsightDetails, LowStockInsightDetails, LowMoverInsightDetails]

    class Config:
        from_attributes = True