from typing import Optional, List
from pydantic import BaseModel, Field, ConfigDict, computed_field

# Importe os outros schemas que este arquivo depende
from .category import CategoryOut

from .rating import RatingsSummaryOut

# Importe seus helpers e enums
from src.core.aws import get_presigned_url
from src.core.utils.enums import CashbackType, ProductType
from .. import ProductVariantLink


# --- Configuração Pydantic Base ---
class AppBaseModel(BaseModel):
    # from_attributes=True permite que o Pydantic leia os dados de modelos SQLAlchemy
    model_config = ConfigDict(from_attributes=True)


# -------------------------------------------------
# 1. Schemas para o WIZARD DE CRIAÇÃO (Entrada da API)
# -------------------------------------------------

class VariantOptionCreateInWizard(AppBaseModel):
    """Representa um complemento (opção) sendo criado dentro do wizard."""
    name_override: str
    price_override: int = 0
    pos_code: Optional[str] = None
    available: bool = True


class VariantCreateInWizard(AppBaseModel):
    """Representa um grupo de complementos (variante) sendo criado dentro do wizard."""
    name: str
    type: str  # Ex: "Ingredientes", "Especificações"
    options: List[VariantOptionCreateInWizard] = []


class ProductCategoryLinkCreate(AppBaseModel):
    """Representa o vínculo do produto a uma categoria no momento da criação."""
    category_id: int
    price_override: Optional[int] = None
    pos_code_override: Optional[str] = None
    available_override: Optional[bool] = None


class ProductVariantLinkCreate(AppBaseModel):
    """Representa a regra de um grupo de complementos para o produto."""
    min_selected_options: int
    max_selected_options: int
    variant_id: int  # Se > 0, vincula um grupo existente. Se < 0, é um novo grupo.
    new_variant_data: Optional[VariantCreateInWizard] = None


class ProductWizardCreate(AppBaseModel):
    """
    Schema principal para receber todos os dados da rota de criação do wizard.
    Este é o corpo (body) da sua requisição POST.
    """
    # Campos base do produto
    name: str
    description: Optional[str] = None
    base_price: int
    cost_price: Optional[int] = 0
    ean: Optional[str] = None
    available: bool = True
    product_type: ProductType = ProductType.INDIVIDUAL
    stock_quantity: Optional[int] = 0
    control_stock: bool = False

    # Listas de vínculos
    category_links: List[ProductCategoryLinkCreate] = Field(..., min_length=1)
    variant_links: List[ProductVariantLinkCreate] = []


# -------------------------------------------------
# 2. Schemas de RESPOSTA DA API (Saída da API)
# -------------------------------------------------

class ProductCategoryLinkOut(AppBaseModel):
    """Como o vínculo entre produto e categoria é retornado na API."""
    category: CategoryOut
    price_override: Optional[int] = None
    pos_code_override: Optional[str] = None
    available_override: Optional[bool] = None


class KitComponentOut(AppBaseModel):
    """Como um componente de um kit é retornado na API."""
    quantity: int
    component: "ProductOut"


class ProductOut(AppBaseModel):
    """
    Schema de resposta completo da API para um produto, com todos os campos e relacionamentos.
    """
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

    # Relacionamentos aninhados
    category_links: List[ProductCategoryLinkOut] = []
    variant_links: List[ProductVariantLink] = []
    components: List[KitComponentOut] = []
    rating: Optional[RatingsSummaryOut] = None

    # Campo computado que não existe no DB, mas é gerado pela API
    @computed_field
    @property
    def image_path(self) -> str | None:
        """Gera a URL da imagem a partir da file_key."""
        if hasattr(self, 'file_key') and self.file_key:
            return get_presigned_url(self.file_key)
        return None


# Permite que o Pydantic resolva a referência circular de `component: "ProductOut"`
KitComponentOut.model_rebuild()


# -------------------------------------------------
# 3. Schemas para AÇÕES EM MASSA (Bulk Actions)
# -------------------------------------------------

class BulkStatusUpdatePayload(BaseModel):
    product_ids: List[int]
    available: bool


class BulkDeletePayload(BaseModel):
    product_ids: List[int]


class BulkCategoryUpdatePayload(BaseModel):
    product_ids: List[int]
    target_category_id: int