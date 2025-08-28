# src/api/schemas/product.py

# ✅ 1. ESSENCIAL: Permite que o Pydantic adie a resolução dos tipos
from __future__ import annotations
from typing import Optional, List
from pydantic import BaseModel, Field, ConfigDict, computed_field

# Importe apenas os schemas que NÃO causam importação circular direta
from .category import CategoryOut
from src.core.aws import get_presigned_url
from src.core.utils.enums import CashbackType, ProductType


# --- Configuração Pydantic Base ---
class AppBaseModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# -------------------------------------------------
# 1. Schemas de ENTRADA da API (Payloads)
# -------------------------------------------------

class VariantOptionCreateInWizard(AppBaseModel):
    name_override: str
    price_override: int = 0
    pos_code: Optional[str] = None
    available: bool = True


class VariantCreateInWizard(AppBaseModel):
    name: str
    type: str
    options: List[VariantOptionCreateInWizard] = []


class ProductCategoryLinkCreate(AppBaseModel):
    category_id: int
    price_override: Optional[int] = None
    pos_code_override: Optional[str] = None
    available_override: Optional[bool] = None


class ProductVariantLinkCreate(AppBaseModel):
    min_selected_options: int
    max_selected_options: int
    variant_id: int
    new_variant_data: Optional[VariantCreateInWizard] = None


class ProductWizardCreate(AppBaseModel):
    name: str
    description: Optional[str] = None
    base_price: int
    cost_price: Optional[int] = 0
    ean: Optional[str] = None
    available: bool = True
    product_type: ProductType = ProductType.INDIVIDUAL
    stock_quantity: Optional[int] = 0
    control_stock: bool = False
    category_links: List[ProductCategoryLinkCreate] = Field(..., min_length=1)
    variant_links: List[ProductVariantLinkCreate] = []


# -------------------------------------------------
# 2. Schemas de RESPOSTA da API (Saída)
# -------------------------------------------------

class KitComponentOut(AppBaseModel):
    quantity: int
    component: "ProductOut"  # ✅ Usando aspas (Forward Reference)


class ProductOut(AppBaseModel):
    id: int
    name: str
    description: Optional[str] = None
    base_price: int
    cost_price: Optional[int] = 0
    available: bool
    priority: int
    promotion_price: Optional[int] = 0
    featured: bool
    activate_promotion: bool
    ean: Optional[str] = None
    stock_quantity: Optional[int] = 0
    control_stock: bool
    min_stock: Optional[int] = 0
    max_stock: Optional[int] = 0
    unit: Optional[str] = "Unidade"
    sold_count: int
    cashback_type: CashbackType
    cashback_value: int
    product_type: ProductType

    # ✅ Usando aspas para todos os tipos aninhados para evitar ciclos
    category_links: List["ProductCategoryLinkOut"] = []
    variant_links: List["ProductVariantLink"] = []
    components: List["KitComponentOut"] = []
    rating: Optional["RatingsSummaryOut"] = None

    # Este campo não precisa estar no DB, ele é gerado na hora
    file_key: Optional[str] = Field(None, exclude=True)

    @computed_field
    @property
    def image_path(self) -> str | None:
        if self.file_key:
            return get_presigned_url(self.file_key)
        return None


# -------------------------------------------------
# 3. Schemas para AÇÕES EM MASSA (Bulk Actions)
# -------------------------------------------------
class ProductCategoryUpdatePayload(BaseModel):
    category_ids: List[int]


class BulkStatusUpdatePayload(BaseModel):
    product_ids: List[int]
    available: bool


class BulkDeletePayload(BaseModel):
    product_ids: List[int]


class BulkCategoryUpdatePayload(BaseModel):
    product_ids: List[int]
    target_category_id: int


# -------------------------------------------------
# 4. RESOLUÇÃO DAS REFERÊNCIAS
#    Importamos os schemas referenciados com aspas e chamamos model_rebuild()
#    Isso deve ser feito no final do arquivo.
# -------------------------------------------------
from .product_category_link import ProductCategoryLinkOut
from .product_variant_link import ProductVariantLink
from .rating import RatingsSummaryOut

KitComponentOut.model_rebuild()
ProductOut.model_rebuild()