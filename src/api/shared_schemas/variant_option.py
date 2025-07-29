# Forward declaration de um schema de produto simplificado para o aninhamento
from typing import Annotated

from pydantic import BaseModel, computed_field, Field

from src.core.models import Variant, ProductVariantLink


class ProductMinimal(BaseModel):
    id: int
    name: str
    base_price: int
    file_key: str | None = None

    @computed_field
    @property
    def image_path(self) -> str | None:
        # from src.core.aws import get_presigned_url
        # return get_presigned_url(self.file_key) if self.file_key else None
        return f"https://s3.aws.com/bucket/{self.file_key}" if self.file_key else None


class VariantOptionBase(BaseModel):
    available: bool = True
    pos_code: Annotated[str | None, Field(max_length=50)] = None

    # Campos para definir um item simples ou sobrepor um produto linkado
    name_override: Annotated[str | None, Field(max_length=100)] = None
    price_override: Annotated[int | None, Field(ge=0, description="Preço em centavos")] = None
    file_key: Annotated[str | None, Field(exclude=True)] = None # Chave da imagem, excluída do JSON de resposta

    # Campo para a mágica do cross-sell
    linked_product_id: int | None = None

class VariantOptionCreate(VariantOptionBase):
    """Schema para criar uma nova opção dentro de um grupo."""
    variant_id: int

class VariantOptionUpdate(VariantOptionBase):
    """Schema para atualizar uma opção existente."""
    pass

class VariantOption(VariantOptionBase):
    """Schema de leitura que resolve inteligentemente os dados da opção."""
    id: int
    variant_id: int
    linked_product: ProductMinimal | None = None # Inclui o objeto produto para os campos computados

    @computed_field
    @property
    def resolved_name(self) -> str:
        """Retorna o nome da opção, priorizando o override e depois o produto linkado."""
        if self.name_override:
            return self.name_override
        if self.linked_product:
            return self.linked_product.name
        return "Opção sem nome" # Fallback

    @computed_field
    @property
    def resolved_price(self) -> int:
        """Retorna o preço da opção, priorizando o override e depois o produto linkado."""
        if self.price_override is not None:
            return self.price_override
        if self.linked_product:
            return self.linked_product.base_price
        return 0 # Fallback

    @computed_field
    @property
    def image_path(self) -> str | None:
        """Retorna o caminho da imagem, priorizando a imagem da opção e depois a do produto linkado."""
        key_to_use = self.file_key or (self.linked_product.file_key if self.linked_product else None)
        if not key_to_use:
            return None
        # from src.core.aws import get_presigned_url
        # return get_presigned_url(key_to_use)
        return f"https://s3.aws.com/bucket/{key_to_use}"


# --- Reconstrução Final ---
# Garante que as referências circulares (strings) sejam resolvidas corretamente
Variant.model_rebuild()
ProductVariantLink.model_rebuild()