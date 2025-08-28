# schemas/product/product_variant_link.py
from __future__ import annotations
from typing import Optional, Annotated, TYPE_CHECKING  # Adicione TYPE_CHECKING
from pydantic import Field

from ..base_schema import AppBaseModel
from src.core.utils.enums import UIDisplayMode

# REMOVA esta importação circular:
# from src.api.schemas.variant.variant import Variant, VariantCreateInWizard

# Use TYPE_CHECKING para importações circulares
if TYPE_CHECKING:
    from src.api.schemas.variant.variant import Variant, VariantCreateInWizard


class ProductVariantLinkCreate(AppBaseModel):
    min_selected_options: int
    max_selected_options: int
    variant_id: int
    new_variant_data: Optional['VariantCreateInWizard'] = None  # Use referência de string


class ProductVariantLinkBase(AppBaseModel):
    ui_display_mode: UIDisplayMode
    min_selected_options: Annotated[int, Field(ge=0, description="0=Opcional, >0=Obrigatório")]
    max_selected_options: Annotated[int, Field(ge=1)]
    max_total_quantity: Annotated[int | None, Field(ge=1)] = None
    display_order: int = 0
    available: bool = True


class ProductVariantLinkCreateFromBase(ProductVariantLinkBase):
    pass


class ProductVariantLinkUpdate(AppBaseModel):
    ui_display_mode: UIDisplayMode | None = None
    min_selected_options: Annotated[int | None, Field(ge=0)] = None
    max_selected_options: Annotated[int | None, Field(ge=1)] = None
    max_total_quantity: Annotated[int | None, Field(ge=1)] = None
    display_order: int | None = None
    available: bool | None = None


class ProductVariantLink(ProductVariantLinkBase):
    variant: 'Variant'  # Use referência de string


# Resolução de referências futuras
ProductVariantLinkCreate.model_rebuild()
ProductVariantLink.model_rebuild()