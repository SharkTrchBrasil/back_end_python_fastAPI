# schemas/product/product_variant_link.py
from __future__ import annotations
from typing import Optional, Annotated
from pydantic import Field

from ..base_schema import AppBaseModel
from ..variant.variant import Variant, VariantCreateInWizard
from src.core.utils.enums import UIDisplayMode


class ProductVariantLinkCreate(AppBaseModel):
    min_selected_options: int
    max_selected_options: int
    variant_id: int
    new_variant_data: Optional[VariantCreateInWizard] = None


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
    variant: Variant


# Resolução de referências futuras
ProductVariantLink.model_rebuild()