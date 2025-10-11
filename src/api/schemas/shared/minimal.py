from __future__ import annotations
from pydantic import Field, computed_field

# ✅ 1. IMPORTAR O ENUM NECESSÁRIO
from src.core.utils.enums import ProductType, ProductStatus
from src.api.schemas.shared.base import AppBaseModel
from src.core.aws import S3_PUBLIC_BASE_URL


# O "cartão de visitas" de um Produto
class ProductMinimal(AppBaseModel):
    id: int
    name: str
    description: str | None = None

    # ✅ 2. ADICIONAR O CAMPO QUE ESTAVA FALTANDO
    product_type: ProductType

    # O campo 'available' parece ser um status mais antigo.
    # Se o seu modelo de produto principal usa 'status', é bom manter a consistência.
    # Por enquanto, manteremos como está para não quebrar outras partes.
    status: ProductStatus | None = None
    stock_quantity: int = 0
    file_key: str | None = Field(None, exclude=True)

    @computed_field
    @property
    def image_path(self) -> str | None:
        return f"{S3_PUBLIC_BASE_URL}/{self.file_key}" if self.file_key else None


# O "cartão de visitas" de uma Categoria
class CategoryMinimal(AppBaseModel):
    id: int
    name: str