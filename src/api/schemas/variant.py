# ARQUIVO: src/api/schemas/variant.py
from typing import Annotated, List
from pydantic import Field

from .base_schema import AppBaseModel, VariantType
from .variant_option import VariantOption, VariantOptionCreate # ✅ IMPORTAÇÃO DIRETA

class VariantBase(AppBaseModel):
    name: Annotated[str, Field(min_length=2, max_length=100, examples=["Adicionais Premium"])]
    type: VariantType

class VariantCreate(VariantBase):
    # Opcional: permitir criar opções junto com o grupo
    options: List[VariantOptionCreate] = []

class VariantUpdate(AppBaseModel):
    name: Annotated[str | None, Field(min_length=2, max_length=100)] = None
    type: VariantType | None = None

class Variant(VariantBase):
    id: int
    # ✅ SEM ASPAS! A referência circular foi eliminada.
    options: List[VariantOption]