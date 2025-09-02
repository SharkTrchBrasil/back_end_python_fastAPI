from __future__ import annotations
from pydantic import Field, computed_field
from .base_schema import AppBaseModel
from src.core.aws import S3_PUBLIC_BASE_URL

# O "cartão de visitas" de um Produto
class ProductMinimal(AppBaseModel):
    id: int
    name: str
    description: str | None = None
    available: bool = True
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