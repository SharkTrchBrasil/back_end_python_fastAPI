from pydantic import BaseModel, ConfigDict

from src.api.schemas.variant import Variant


class ProductVariantProductSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    variant_id: int
    product_id: int
    variant: Variant  # ⬅️ inclui a variante completa com opções
