# ===================================================================
# ARQUIVO: src/api/shared_schemas/variant.py
# ===================================================================
from typing import Annotated, List
from pydantic import Field
from .base_schema import AppBaseModel, VariantType # CORRECT: Importa da base de schemas

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
    # CORRECT: Usa uma string para a referência, que será resolvida depois
    options: List["VariantOption"]

# 1. Importamos a classe que prometemos (VariantOptionOut) DEPOIS da definição da classe atual.
from .variant_option import VariantOption

# 2. Agora que VariantOptionOut é conhecido, mandamos o Pydantic resolver a promessa.
Variant.model_rebuild()

