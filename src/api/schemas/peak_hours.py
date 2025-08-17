# Em schemas.py

from pydantic import BaseModel, Field

class PeakHoursAnalytics(BaseModel):
    lunch_peak_start: str = Field(..., alias="lunchPeakStart")
    lunch_peak_end: str = Field(..., alias="lunchPeakEnd")
    dinner_peak_start: str = Field(..., alias="dinnerPeakStart")
    dinner_peak_end: str = Field(..., alias="dinnerPeakEnd")

    class Config:
        populate_by_name = True # Permite popular com camelCase (do dicionário)
        from_attributes = True # Necessário se for validar a partir de um objeto