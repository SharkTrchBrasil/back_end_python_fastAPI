from pydantic import BaseModel
from typing import List, Optional

# Importe o novo schema
from src.api.schemas.store.location.store_neighborhood import StoreNeighborhoodSchema, NeighborhoodNestedInputSchema


# ATUALIZADO: Schema para criação/atualização
class StoreCityUpsertSchema(BaseModel):
    id: Optional[int] = None # Essencial para saber se é uma cidade nova ou existente
    name: str
    delivery_fee: int = 0
    is_active: bool = True
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    neighborhoods: List[NeighborhoodNestedInputSchema] = [] # Usa o novo schema aninhado

    model_config = {
        "from_attributes": True,
        "arbitrary_types_allowed": True
    }

# Schema de saída (quando você busca uma cidade)
class StoreCitySchema(BaseModel):
    id: int
    name: str
    delivery_fee: int = 0
    is_active: bool = True
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    neighborhoods: List[StoreNeighborhoodSchema] = []

    model_config = {
        "from_attributes": True,
        "arbitrary_types_allowed": True
    }

# Output: só retorna o id (se ainda precisar dele)
class StoreCityOut(BaseModel):
    id: int

    class Config:
        orm_mode = True