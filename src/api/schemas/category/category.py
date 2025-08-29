from decimal import Decimal
from pydantic import Field, computed_field
from typing import Optional

from src.core.aws import get_presigned_url
from src.core.models import CashbackType
from ..base_schema import AppBaseModel

class CategoryBase(AppBaseModel):
    name: str
    priority: int
    is_active: bool

class CategoryCreate(CategoryBase):
    cashback_type: CashbackType = Field(default=CashbackType.NONE)
    cashback_value: Decimal = Field(default=Decimal('0.00'))

class CategoryUpdate(AppBaseModel):
    name: Optional[str] = None
    priority: Optional[int] = None
    is_active: Optional[bool] = None
    cashback_type: Optional[CashbackType] = None
    cashback_value: Optional[Decimal] = None

class CategoryOut(CategoryBase):
    id: int
    file_key: str = Field(exclude=True)
    cashback_type: CashbackType
    cashback_value: Decimal

    @computed_field
    @property
    def image_path(self) -> Optional[str]:
        return get_presigned_url(self.file_key) if self.file_key else None