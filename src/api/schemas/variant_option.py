# ARQUIVO: src/api/schemas/variant_option.py
from typing import Annotated
from pydantic import Field, computed_field

from src.api.schemas.base_schema import AppBaseModel
from src.api.schemas.product_minimal import ProductMinimal
from src.core.aws import get_presigned_url


# ✅ IMPORTAÇÃO LIMPA DO ARQUIVO COMPARTILHADO

# --- SCHEMA BASE ATUALIZADO ---
class VariantOptionBase(AppBaseModel):
    available: bool = True
    pos_code: Annotated[str | None, Field(max_length=50)] = None
    name_override: Annotated[str | None, Field(max_length=100)] = None
    price_override: Annotated[int | None, Field(ge=0, description="Preço em centavos")] = None
    file_key: Annotated[str | None, Field(exclude=True)] = None
    linked_product_id: int | None = None
    description: Annotated[str | None, Field(max_length=1000)] = None
    track_inventory: bool = Field(default=False)
    stock_quantity: Annotated[int, Field(ge=0)] = Field(default=0)

class VariantOptionCreate(VariantOptionBase):
    variant_id: int

class VariantOptionUpdate(VariantOptionBase):
    # Permite atualizar todos os campos da base
    # Para Pydantic v2, não precisa listar todos os campos com Optional
    # A menos que queira um comportamento específico.
    # Esta classe pode até ser removida se o PATCH usar o modelo Base diretamente.
    pass

# --- SCHEMA DE SAÍDA (RESPOSTA DA API) ATUALIZADO ---
class VariantOption(VariantOptionBase):
    id: int
    variant_id: int
    linked_product: ProductMinimal | None = None

    @computed_field
    @property
    def resolved_name(self) -> str:
        # (seu código aqui, sem alterações)
        if self.name_override:
            return self.name_override
        if self.linked_product:
            return self.linked_product.name
        return "Opção sem nome"

    @computed_field
    @property
    def resolved_price(self) -> int:
        # (seu código aqui, sem alterações)
        if self.price_override is not None:
            return self.price_override
        if self.linked_product:
            return self.linked_product.base_price
        return 0

    @computed_field
    @property
    def image_path(self) -> str | None:
        # (seu código aqui, sem alterações)
        key_to_use = self.file_key or (self.linked_product.file_key if self.linked_product else None)
        return get_presigned_url(key_to_use) if key_to_use else None

    @computed_field
    @property
    def is_actually_available(self) -> bool:
        # (seu código aqui, sem alterações)
        if not self.available:
            return False
        if not self.track_inventory:
            return True
        return self.stock_quantity > 0