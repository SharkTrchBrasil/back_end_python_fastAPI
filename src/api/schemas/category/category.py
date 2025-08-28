# schemas/category/category.py
from decimal import Decimal
from pydantic import Field, computed_field
from typing import Optional

from src.core.aws import get_presigned_url
from src.core.models import CashbackType

from ..base_schema import AppBaseModel


class CategoryBase(AppBaseModel):
    """Campos base de uma categoria."""
    name: str
    priority: int
    is_active: bool


class CategoryCreate(CategoryBase):
    """Schema para criar uma nova categoria, com campos de cashback opcionais."""
    cashback_type: CashbackType = Field(default=CashbackType.NONE)
    cashback_value: Decimal = Field(default=Decimal('0.00'))


class CategoryUpdate(AppBaseModel):
    """Schema para atualizar uma categoria, todos os campos são opcionais."""
    name: Optional[str] = None
    priority: Optional[int] = None
    is_active: Optional[bool] = None
    cashback_type: Optional[CashbackType] = None
    cashback_value: Optional[Decimal] = None


class CategoryOut(CategoryBase):
    """Schema de resposta da API, incluindo os dados de cashback."""
    id: int
    file_key: str = Field(exclude=True)
    cashback_type: CashbackType
    cashback_value: Decimal

    @computed_field
    @property
    def image_path(self) -> Optional[str]:
        """Gera a URL da imagem a partir da file_key."""
        return get_presigned_url(self.file_key) if self.file_key else None