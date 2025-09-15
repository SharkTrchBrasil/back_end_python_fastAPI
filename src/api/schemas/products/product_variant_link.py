# ARQUIVO CORRIGIDO: src/api/schemas/products/product_variant_link.py

from __future__ import annotations
from typing import Optional, List
from pydantic import BaseModel, Field

from src.api.schemas.products.variant import Variant
from src.api.schemas.products.variant_option import VariantOptionCreate, OptionInVariantLink
from src.api.schemas.shared.base import AppBaseModel, UIDisplayMode, VariantType


# --- 1. Schemas de Base (Estrutura Comum) ---

class ProductVariantLinkBase(AppBaseModel):
    ui_display_mode: UIDisplayMode
    min_selected_options: int = Field(..., ge=0, description="0=Opcional, >0=Obrigatório")
    max_selected_options: int = Field(..., ge=1)
    available: bool = True
    # Campos que parecem ter sido removidos do seu código mais recente, mas que podem ser úteis:
    # max_total_quantity: Optional[int] = Field(None, ge=1)
    # display_order: int = 0


# --- 2. Schemas de Entrada (Payloads que o Flutter envia para a API) ---

class VariantInLink(BaseModel):
    """Schema para o objeto 'variant' que vem ANINHADO do Flutter."""
    id: int | None = None # Pode ser negativo/nulo (novo) ou positivo (existente)
    name: str
    type: VariantType
    options: List[OptionInVariantLink] = []

class ProductVariantLinkCreate(ProductVariantLinkBase):
    """
    Schema para um link de complemento que vem do Flutter.
    SEMPRE contém o objeto 'variant' completo.
    A lógica do backend decide se o 'variant' é novo ou existente pelo ID.
    """
    # ✅ CORREÇÃO PRINCIPAL: O campo agora se chama 'variant'
    variant: VariantInLink


class ProductVariantLinkUpdate(AppBaseModel):
    """Schema para atualizar APENAS as regras de um link JÁ EXISTENTE."""
    ui_display_mode: Optional[UIDisplayMode] = None
    min_selected_options: Optional[int] = Field(None, ge=0)
    max_selected_options: Optional[int] = Field(None, ge=1)
    available: Optional[bool] = None


# --- 3. Schemas de Saída (Respostas da API para o Flutter) ---

class ProductVariantLinkOut(ProductVariantLinkBase):
    """
    Schema de resposta da API. Retorna os dados do vínculo
    e o objeto Variant completo aninhado.
    """
    id: int
    variant: Variant # Usa o schema de saída para Variant