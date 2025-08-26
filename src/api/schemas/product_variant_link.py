# ===================================================================
# ARQUIVO: src/api/shared_schemas/product_variant_link.py
# ===================================================================
from typing import Annotated
from pydantic import Field
from .base_schema import AppBaseModel, UIDisplayMode # CORRECT: Importa da base de schemas

class ProductVariantLinkBase(AppBaseModel):
    ui_display_mode: UIDisplayMode
    min_selected_options: Annotated[int, Field(ge=0, description="0=Opcional, >0=Obrigatório")]
    max_selected_options: Annotated[int, Field(ge=1)]
    max_total_quantity: Annotated[int | None, Field(ge=1)] = None
    display_order: int = 0
    available: bool = True

class ProductVariantLinkCreate(ProductVariantLinkBase):
    pass

class ProductVariantLinkUpdate(AppBaseModel):
    ui_display_mode: UIDisplayMode | None = None
    min_selected_options: Annotated[int | None, Field(ge=0)] = None
    max_selected_options: Annotated[int | None, Field(ge=1)] = None
    max_total_quantity: Annotated[int | None, Field(ge=1)] = None
    display_order: int | None = None
    available: bool | None = None

class ProductVariantLink(ProductVariantLinkBase):
    # CORRECT: Usa uma string para a referência, que será resolvida depois
    variant: "Variant"


