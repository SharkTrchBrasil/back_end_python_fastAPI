# schemas/product/product_category_link.py
from typing import Optional

from pydantic import BaseModel


class ProductCategoryLinkCreate(BaseModel):
    """Schema usado apenas na criação de produtos (wizard)"""
    category_id: int
    price_override: Optional[int] = None
    pos_code_override: Optional[str] = None
    available_override: Optional[bool] = None