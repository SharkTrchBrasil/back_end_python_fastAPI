from typing import Annotated, List

from pydantic import Field, BaseModel

from src.core.models import VariantType, VariantOption


class VariantBase(BaseModel):
    """Campos base para um template de grupo de complementos."""
    name: Annotated[str, Field(min_length=2, max_length=100, examples=["Adicionais Premium"])]
    type: VariantType

class VariantCreate(VariantBase):
    """Schema para criar um novo template de grupo na API."""
    pass

class VariantUpdate(BaseModel):
    """Schema para atualizar um template, todos os campos são opcionais."""
    name: Annotated[str | None, Field(min_length=2, max_length=100)] = None
    type: VariantType | None = None

class Variant(VariantBase):
    """Schema para ler os dados de um template, incluindo suas opções."""
    id: int
    options: List["VariantOption"] # Referência circular resolvida no final


Variant.model_rebuild()

