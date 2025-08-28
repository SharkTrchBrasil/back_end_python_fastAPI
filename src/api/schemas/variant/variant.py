# schemas/variant/variant.py
from __future__ import annotations
from typing import Annotated, List
from pydantic import Field

from src.core.utils.enums import VariantType
from .variant_option_wizard import VariantOptionCreateInWizard
from ..base_schema import AppBaseModel

from .variant_option import VariantOption


class VariantBase(AppBaseModel):
    name: Annotated[str, Field(min_length=2, max_length=100, examples=["Adicionais Premium"])]
    type: VariantType


class VariantCreate(VariantBase):
    pass


class VariantUpdate(AppBaseModel):
    name: Annotated[str | None, Field(min_length=2, max_length=100)] = None
    type: VariantType | None = None


class Variant(VariantBase):
    id: int
    options: List[VariantOption]


class VariantCreateInWizard(AppBaseModel):
    name: str
    type: str
    options: List[VariantOptionCreateInWizard] = []




Variant.model_rebuild()



