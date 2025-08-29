# ARQUIVO: src/api/schemas/product_variant_link.py
from typing import Annotated, Optional
from pydantic import Field

from .base_schema import AppBaseModel, UIDisplayMode
# Supondo que você tenha um base.py
from .variant import Variant, VariantCreate  # ✅ IMPORTAÇÃO DIRETA: Importa o schema Variant


class ProductVariantLinkBase(AppBaseModel):
    ui_display_mode: UIDisplayMode
    min_selected_options: Annotated[int, Field(ge=0, description="0=Opcional, >0=Obrigatório")]
    max_selected_options: Annotated[int, Field(ge=1)]
    max_total_quantity: Optional[int] = Field(None, ge=1)
    display_order: int = 0
    available: bool = True


class ProductVariantLinkCreate(ProductVariantLinkBase):
    """
    Schema usado no wizard de criação de produto.
    Inclui campos para vincular um grupo existente ou criar um novo.
    """
    variant_id: Optional[int] = None  # ID de um grupo existente
    new_variant_data: Optional[VariantCreate] = None  # Dados para criar um novo grupo


class ProductVariantLinkUpdate(AppBaseModel):
    ui_display_mode: Optional[UIDisplayMode] = None
    min_selected_options: Optional[Annotated[int, Field(ge=0)]] = None
    max_selected_options: Optional[Annotated[int, Field(ge=1)]] = None
    max_total_quantity: Optional[int] = Field(None, ge=1)
    display_order: Optional[int] = None
    available: Optional[bool] = None


# ✅ DEFINIÇÃO CORRETA DO SCHEMA DE SAÍDA (OUT)
class ProductVariantLinkOut(ProductVariantLinkBase):
    """
    Schema de resposta da API. Retorna os dados do vínculo
    e o objeto Variant completo aninhado.
    """
    id: int  # Um schema de saída deve ter o ID do registro no banco

    # ✅ SEM ASPAS: A classe Variant foi importada diretamente.
    variant: Variant