# src/api/shared_schemas/store_neighborhood.py (ou onde estiver)
from pydantic import BaseModel, ConfigDict # Importe ConfigDict para Pydantic V2

class StoreNeighborhoodBaseSchema(BaseModel):
    name: str
    city_id: int
    delivery_fee: int = 0
    free_delivery: bool = False
    is_active: bool = True

    model_config = ConfigDict(
        from_attributes=True,
        arbitrary_types_allowed=True
    )

class StoreNeighborhoodSchema(StoreNeighborhoodBaseSchema):
    id: int

    # Use model_config para Pydantic V2 para consistência
    model_config = ConfigDict(
        from_attributes=True,
        arbitrary_types_allowed=True
    )
    # Se você removeu 'arbitrary_types_allowed' de StoreNeighborhoodBaseSchema
    # e ainda tem problemas, pode ser que você precise dessa linha aqui também