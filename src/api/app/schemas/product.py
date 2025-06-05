from pydantic import BaseModel, Field, computed_field, ConfigDict


from src.api.app.schemas.category import Category
from src.api.app.schemas.product_variant_product import ProductVariantProductSchemaApp
from src.api.app.schemas.variants import VariantOption
from src.core.aws import get_presigned_url




class Product(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    description: str
    base_price: int
    category: Category
    variant_links: list[ProductVariantProductSchemaApp]
    options: list[VariantOption]  # se quiser já trazer junto
    file_key: str = Field(exclude=True)

    @computed_field
    @property
    def image_path(self) -> str:
        return get_presigned_url(self.file_key)

