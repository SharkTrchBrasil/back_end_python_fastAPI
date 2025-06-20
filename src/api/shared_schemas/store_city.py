from pydantic import BaseModel
from typing import Optional, List

# IMPORTANTE: Importe o Pydantic Model de Bairro, não o modelo SQLAlchemy
from src.api.shared_schemas.store_neighborhood import StoreNeighborhoodBaseSchema # Ou StoreNeighborhoodSchema, dependendo de qual você usa para aninhamento


class StoreCityBaseSchema(BaseModel):
    name: str
    delivery_fee: int = 0
    is_active: bool = True
    # CORREÇÃO AQUI: neighborhoods deve ser uma lista do SEU PYDANTIC MODEL de bairro
    neighborhoods: List[StoreNeighborhoodBaseSchema] = []  # Agora é uma lista de Pydantic Models


    model_config = {
        "from_attributes": True,
        "arbitrary_types_allowed": True # Mantenha esta linha
    }

class StoreCitySchema(StoreCityBaseSchema):
    id: int
