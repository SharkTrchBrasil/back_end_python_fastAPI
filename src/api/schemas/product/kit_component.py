# schemas/product/kit_component.py
from __future__ import annotations
from typing import TYPE_CHECKING  # Adicione TYPE_CHECKING
from ..base_schema import AppBaseModel

# REMOVA esta importação circular:
# from .product import ProductOut

# Use TYPE_CHECKING para importação circular
if TYPE_CHECKING:
    from .product import ProductOut


class KitComponentOut(AppBaseModel):
    quantity: int
    component: 'ProductOut'  # Use referência de string


# Resolução de referências futuras
KitComponentOut.model_rebuild()