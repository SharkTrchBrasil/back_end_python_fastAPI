from pydantic import BaseModel, ConfigDict

from src.api.app.schemas.product import ProductVariant


class ProductVariantProductSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    variant_id: int
    product_id: int
    variant: ProductVariant  # ⬅️ inclui a variante completa com opções
