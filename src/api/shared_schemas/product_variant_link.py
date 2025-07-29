from typing import Annotated

from pydantic import Field, BaseModel

from src.core.models import Variant, UIDisplayMode


class ProductVariantLinkBase(BaseModel):
    """Campos base que definem as regras de um grupo em um produto."""
    ui_display_mode: UIDisplayMode
    min_selected_options: Annotated[int, Field(ge=0, description="0=Opcional, >0=Obrigatório")]
    max_selected_options: Annotated[int, Field(ge=1)]
    max_total_quantity: Annotated[int | None, Field(ge=1, description="Soma total das quantidades se houver repetição")] = None
    display_order: int = 0
    available: bool = True

class ProductVariantLinkCreate(ProductVariantLinkBase):
    """Schema para criar a ligação entre um produto e um grupo (a 'cópia')."""
    # product_id e variant_id virão dos parâmetros da URL na API (ex: /products/{pid}/variants/{vid})
    pass

class ProductVariantLinkUpdate(BaseModel):
    """Schema para atualizar as regras de uma ligação existente."""
    ui_display_mode: UIDisplayMode | None = None
    min_selected_options: Annotated[int | None, Field(ge=0)] = None
    max_selected_options: Annotated[int | None, Field(ge=1)] = None
    max_total_quantity: Annotated[int | None, Field(ge=1)] = None
    display_order: int | None = None
    available: bool | None = None

class ProductVariantLink(ProductVariantLinkBase):
    """Schema para ler as regras de um grupo em um produto, incluindo o template Variant aninhado."""
    variant: Variant # Retorna o template completo que está sendo usado