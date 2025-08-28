# schemas/product/kit_component.py
from __future__ import annotations
from ..base_schema import AppBaseModel
from .product import ProductOut


class KitComponentOut(AppBaseModel):
    quantity: int
    component: ProductOut


# Resolução de referências futuras
KitComponentOut.model_rebuild()