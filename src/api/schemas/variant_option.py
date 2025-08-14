from typing import Annotated
from pydantic import Field, computed_field
from .base_schema import AppBaseModel  # Importa da base de schemas
from src.core.aws import get_presigned_url


class ProductMinimal(AppBaseModel):
    id: int
    name: str
    base_price: int
    file_key: str | None = None

    # Este campo permanece o mesmo
    @computed_field
    @property
    def image_path(self) -> str:
        return get_presigned_url(self.file_key)


# ✅ --- SCHEMA BASE ATUALIZADO --- ✅
class VariantOptionBase(AppBaseModel):
    available: bool = True
    pos_code: Annotated[str | None, Field(max_length=50)] = None
    name_override: Annotated[str | None, Field(max_length=100)] = None
    price_override: Annotated[int | None, Field(ge=0, description="Preço em centavos")] = None
    file_key: Annotated[str | None, Field(exclude=True)] = None
    linked_product_id: int | None = None

    # ✅ 1. CAMPO DE DESCRIÇÃO ADICIONADO
    description: Annotated[str | None, Field(max_length=1000)] = None

    # ✅ 2. CAMPOS DE CONTROLE DE ESTOQUE ADICIONADOS
    track_inventory: bool = Field(default=False, description="Se True, o estoque será controlado")
    stock_quantity: Annotated[int, Field(ge=0)] = Field(default=0,
                                                        description="Quantidade em estoque. Relevante apenas se track_inventory for True")


class VariantOptionCreate(VariantOptionBase):
    variant_id: int


class VariantOptionUpdate(VariantOptionBase):
    pass


# ✅ --- SCHEMA DE SAÍDA (RESPOSTA DA API) ATUALIZADO --- ✅
class VariantOption(VariantOptionBase):
    id: int
    variant_id: int
    linked_product: ProductMinimal | None = None

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
        key_to_use = self.file_key or (self.linked_product.file_key if self.linked_product else None)
        if not key_to_use:
            return None
        # A lógica da URL assinada deve ser usada aqui também
        return get_presigned_url(key_to_use)

    # ✅ 3. PROPRIEDADE INTELIGENTE DE DISPONIBILIDADE ADICIONADA
    @computed_field
    @property
    def is_actually_available(self) -> bool:
        """
        Calcula a disponibilidade real do item para o front-end.
        """
        # Se desabilitado manualmente, está indisponível.
        if not self.available:
            return False
        # Se o estoque não é rastreado, está disponível.
        if not self.track_inventory:
            return True
        # Se o estoque é rastreado, depende da quantidade.
        return self.stock_quantity > 0