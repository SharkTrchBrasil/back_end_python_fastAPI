# ARQUIVO: src/api/schemas/variant.py
from typing import Annotated, List
from pydantic import Field

from src.api.schemas.shared.base import AppBaseModel, VariantType
from .product_variant_link import VariantLinkRuleUpdate
from .variant_option import VariantOption, WizardVariantOptionCreate, OptionForVariantUpdate


class VariantBase(AppBaseModel):
    name: Annotated[str, Field(min_length=2, max_length=100, examples=["Adicionais Premium"])]
    type: VariantType
    # ✅ CAMPO ADICIONADO AQUI
    # O nome `is_available` corresponde exatamente ao do modelo SQLAlchemy
    is_available: bool = Field(True, description="Controla se o grupo está ativo ou pausado")

class VariantCreate(VariantBase):
    # Opcional: permitir criar opções junto com o grupo
    options: List[WizardVariantOptionCreate] = []

class VariantUpdate(AppBaseModel):
    name: Annotated[str | None, Field(min_length=2, max_length=100)] = None
    type: VariantType | None = None
    # ✅ CAMPO ADICIONADO AQUI TAMBÉM (opcional)
    is_available: bool | None = None
    options: list[OptionForVariantUpdate] | None = None
    linked_products_rules: list[VariantLinkRuleUpdate] | None = None


class Variant(VariantBase):
    id: int
    # A classe de saída 'Variant' herda automaticamente o campo `is_available` da `VariantBase`
    options: List[VariantOption]