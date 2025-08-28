# schemas/category/product_category_link.py
from __future__ import annotations
from typing import Optional, TYPE_CHECKING
from pydantic import Field

from ..base_schema import AppBaseModel


class ProductCategoryLinkBase(AppBaseModel):
    price_override: Optional[int] = None
    pos_code_override: Optional[str] = None
    available_override: Optional[bool] = None


class ProductCategoryLinkCreate(ProductCategoryLinkBase):
    category_id: int


class ProductCategoryLinkOut(ProductCategoryLinkBase):
    """
    Schema de resposta da API para o vínculo entre um Produto e uma Categoria.
    Mostra a qual categoria o produto está vinculado e se há alguma
    regra especial (como preço diferente) apenas para essa categoria.
    """
    id: int
    product_id: int
    category_id: int
    category: CategoryOut  # Referência futura


# REMOVA estas linhas:
# from .category import CategoryOut
# ProductCategoryLinkOut.model_rebuild()

# Use TYPE_CHECKING:
if TYPE_CHECKING:
    from .category import CategoryOut