from pydantic import BaseModel, ConfigDict
from typing import Optional

# NOVO: Schema para a entrada aninhada dentro da cidade
class NeighborhoodNestedInputSchema(BaseModel):
    id: Optional[int] = None # Essencial para saber se é um bairro novo ou existente
    name: str
    delivery_fee: int = 0
    is_active: bool = True

    model_config = ConfigDict(
        from_attributes=True,
    )

class StoreNeighborhoodBaseSchema(BaseModel):
    name: str
    city_id: int
    delivery_fee: int = 0
    free_delivery: bool = False
    is_active: bool = True

    model_config = ConfigDict(
        from_attributes=True,
        arbitrary_types_allowed=True,
    )

class StoreNeighborhoodSchema(StoreNeighborhoodBaseSchema):
    id: int

    model_config = ConfigDict(
        from_attributes=True,
        arbitrary_types_allowed=True,
    )