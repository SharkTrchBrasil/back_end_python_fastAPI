from pydantic import BaseModel, ConfigDict

class ProductVariantProductSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    variant_id: int
    product_id: int
