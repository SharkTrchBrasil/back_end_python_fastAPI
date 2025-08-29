from __future__ import annotations
from typing import TYPE_CHECKING
from ..base_schema import AppBaseModel

if TYPE_CHECKING:
    from .product import ProductOut

class KitComponentOut(AppBaseModel):
    quantity: int
    component: 'ProductOut'