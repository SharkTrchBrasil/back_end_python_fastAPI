# ✅ SUBSTITUA o arquivo INTEIRO por este código:

from __future__ import annotations
from typing import Optional
from pydantic import Field

from src.api.schemas.base_schema import AppBaseModel
from src.api.schemas.category.category import CategoryOut  # IMPORT DIRETO

class ProductCategoryLinkBase(AppBaseModel):
    price_override: Optional[int] = None
    pos_code_override: Optional[str] = None
    available_override: Optional[bool] = None

class ProductCategoryLinkCreate(ProductCategoryLinkBase):
    category_id: int

class ProductCategoryLinkOut(ProductCategoryLinkBase):
    id: int
    product_id: int
    category_id: int
    category: CategoryOut  # USA IMPORT DIRETO