from __future__ import annotations

from typing import Annotated
from pydantic import Field, computed_field

from src.api.schemas.shared.base import AppBaseModel
from src.api.schemas.shared.minimal import ProductMinimal  # Garanta que este import está correto
from src.core.aws import S3_PUBLIC_BASE_URL


# --- SCHEMA BASE ATUALIZADO ---
class VariantOptionBase(AppBaseModel):
    available: bool = True
    pos_code: Annotated[str | None, Field(max_length=50)] = None
    name_override: Annotated[str | None, Field(max_length=100)] = None
    price_override: Annotated[int | None, Field(ge=0, description="Preço em centavos")] = None
    linked_product_id: int | None = None
    description: Annotated[str | None, Field(max_length=1000)] = None
    track_inventory: bool = Field(default=False)
    stock_quantity: Annotated[int, Field(ge=0)] = Field(default=0)


    file_key: str | None = None

class VariantOptionCreate(VariantOptionBase):
    variant_id: int

class WizardVariantOptionCreate(VariantOptionBase):
    pass # Herda tudo da base, sem adicionar o variant_id


class VariantOptionUpdate(AppBaseModel):
    available: bool | None = None
    pos_code: Annotated[str | None, Field(max_length=50)] = None
    name_override: Annotated[str | None, Field(max_length=100)] = None
    price_override: Annotated[int | None, Field(ge=0)] = None
    linked_product_id: int | None = None
    description: Annotated[str | None, Field(max_length=1000)] = None
    track_inventory: bool | None = None
    stock_quantity: Annotated[int | None, Field(ge=0)] = None



# --- SCHEMA DE SAÍDA (RESPOSTA DA API) ATUALIZADO ---
class VariantOption(VariantOptionBase):
    id: int
    variant_id: int
    linked_product: ProductMinimal | None = None

    # ✅ CORREÇÃO: file_key adicionado aqui para ser lido do banco.
    # O `exclude=True` impede que a chave interna seja exposta na API.
    file_key: str | None = Field(None, exclude=True)

    @computed_field
    @property
    def resolved_name(self) -> str:
        if self.name_override:
            return self.name_override
        if self.linked_product:
            return self.linked_product.name
        return "Opção sem nome"


    # ✅ CORREÇÃO APLICADA AQUI
    @computed_field
    @property
    def resolved_price(self) -> int:
        """
        Retorna o preço da opção. A regra de negócio é que ele é SEMPRE
        o price_override, ou 0 se não for definido.
        """
        return self.price_override if self.price_override is not None else 0

        # ✅ 2. LÓGICA DO `image_path` TOTALMENTE CORRIGIDA

    @computed_field
    @property
    def image_path(self) -> str | None:
        """
        Gera a URL da imagem seguindo a hierarquia correta:
        1. Imagem da própria opção (se existir).
        2. Se não, imagem do produto vinculado (se existir).
        3. Se não, nulo.
        """
        key_to_use = self.file_key or (self.linked_product.file_key if self.linked_product else None)
        return f"{S3_PUBLIC_BASE_URL}/{key_to_use}" if key_to_use else None

    @computed_field
    @property
    def is_actually_available(self) -> bool:
        if not self.available:
            return False
        if not self.track_inventory:
            return True
        return self.stock_quantity > 0