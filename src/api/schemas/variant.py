# ===================================================================
# ARQUIVO: src/api/shared_schemas/variant.py
# ===================================================================
from __future__ import annotations
from typing import Annotated, List
from pydantic import Field
from .base_schema import AppBaseModel, VariantType


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
    options: List["VariantOption"]  # <- referência como string


# -------------------------------------------------
# RESOLUÇÃO DA REFERÊNCIA FUTURA
# -------------------------------------------------
from .variant_option import VariantOption  # import atrasado
Variant.model_rebuild()
