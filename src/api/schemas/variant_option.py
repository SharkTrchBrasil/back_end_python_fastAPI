# ARQUIVO: src/api/schemas/variant_option.py
from typing import Annotated
from pydantic import Field, computed_field

from src.api.schemas.base_schema import AppBaseModel
from src.api.schemas.product_minimal import ProductMinimal  # Garanta que este import está correto
from src.core.aws import get_presigned_url


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
    # ✅ CORREÇÃO: file_key adicionado à base para que possa ser criado
    # Não precisa ser enviado no JSON de criação, pois virá do upload do arquivo.


class VariantOptionCreate(VariantOptionBase):
    variant_id: int


class VariantOptionUpdate(AppBaseModel):
    available: bool | None = None
    pos_code: Annotated[str | None, Field(max_length=50)] = None
    name_override: Annotated[str | None, Field(max_length=100)] = None
    price_override: Annotated[int | None, Field(ge=0)] = None
    linked_product_id: int | None = None
    description: Annotated[str | None, Field(max_length=1000)] = None
    track_inventory: bool | None = None
    stock_quantity: Annotated[int | None, Field(ge=0)] = None
    # ✅ CORREÇÃO: file_key não é atualizado via JSON, mas sim via upload,
    # então não precisa estar aqui.


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

    @computed_field
    @property
    def resolved_price(self) -> int:
        if self.price_override is not None:
            return self.price_override
        if self.linked_product:
            return self.linked_product.base_price
        return 0

    @computed_field
    @property
    def image_path(self) -> str | None:
        # Agora `self.file_key` existe e este código funcionará.
        key_to_use = self.file_key or (self.linked_product.file_key if self.linked_product else None)
        return get_presigned_url(key_to_use) if key_to_use else None

    @computed_field
    @property
    def is_actually_available(self) -> bool:
        if not self.available:
            return False
        if not self.track_inventory:
            return True
        return self.stock_quantity > 0