from __future__ import annotations


from pydantic import BaseModel, Field, computed_field

from src.api.schemas.products.product_category_link import ProductCategoryLinkOut
from src.core.aws import S3_PUBLIC_BASE_URL
from src.core.models import CategoryType, CashbackType
from decimal import Decimal


# --- Schemas para Itens e Grupos de Opções ---

class OptionItemBase(BaseModel):
    name: str
    description: str | None = None
    price: float = 0.0
    is_active: bool = True


class OptionItemCreate(OptionItemBase):
    pass


class OptionItem(OptionItemBase):
    id: int
    priority: int

    class Config: from_attributes = True


class OptionGroupBase(BaseModel):
    name: str
    min_selection: int = 1
    max_selection: int = 1


class OptionGroupCreate(OptionGroupBase):
    pass


class OptionGroup(OptionGroupBase):
    id: int
    priority: int
    items: list[OptionItem] = []

    class Config: from_attributes = True


# --- Schemas principais de Categoria (Atualizados) ---

class CategoryBase(BaseModel):
    name: str
    is_active: bool = True
    type: CategoryType


class CategoryCreate(CategoryBase):
    pass  # Para criar, só precisamos do nome e tipo, o resto vem depois


class CategoryUpdate(BaseModel):
    name: str | None = None
    is_active: bool | None = None
    priority: int | None = None
    # Adicione aqui outros campos que podem ser atualizados
    cashback_type: CashbackType | None = None
    cashback_value: Decimal | None = None


class Category(CategoryBase):  # O schema de resposta
    id: int
    priority: int

    # ✨ CORREÇÃO 1: Adicionar a URL da imagem para o frontend
    file_key: str | None = Field(None, exclude=True)  # Exclui do JSON final

    @computed_field
    @property
    def image_path(self) -> str | None:
        """Gera a URL completa e pública da imagem."""
        if self.file_key:
            return f"{S3_PUBLIC_BASE_URL}/{self.file_key}"
        return None

    # ✨ CORREÇÃO 2: Cashback não é opcional, pois sempre terá um valor padrão
    cashback_type: CashbackType
    cashback_value: Decimal
    product_links: list[ProductCategoryLinkOut] = []

    option_groups: list[OptionGroup] = []

    class Config:
        from_attributes = True







