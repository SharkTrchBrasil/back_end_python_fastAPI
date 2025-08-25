from typing import Optional, List
from pydantic import BaseModel, Field, ConfigDict, computed_field

from .category import CategoryOut
from .product_variant_link import ProductVariantLink as ProductVariantLinkOut

from src.core.aws import get_presigned_url
from src.core.utils.enums import CashbackType, ProductType
from .rating import RatingsSummaryOut


# --- Configuração Pydantic Base ---
class AppBaseModel(BaseModel):
    model_config = ConfigDict(from_attributes=True, extra="forbid")

# -------------------------------------------------
# 1. Schemas de Produto
# -------------------------------------------------


class KitComponentOut(AppBaseModel):
    quantity: int
    # Inclui os dados do produto componente para o front-end saber o que é
    component: "ProductOut"

# Crie este schema Pydantic para o corpo da requisição
class BulkStatusUpdatePayload(BaseModel):
    product_ids: List[int]
    available: bool


class BulkDeletePayload(BaseModel):
    product_ids: List[int]

class Product(AppBaseModel):
    """Campos essenciais que definem um produto."""
    name: str
    description: str
    base_price: int
    product_type: ProductType = ProductType.INDIVIDUAL
    available: bool
    promotion_price: int
    featured: bool
    activate_promotion: bool
    ean: str
    cost_price: int
    stock_quantity: int
    control_stock: bool
    min_stock: int
    max_stock: int
    unit: str
    sold_count: int
    file_key: str | None = Field(default=None, exclude=True) # Exclui do JSON de resposta

    cashback_type: CashbackType = CashbackType.NONE
    cashback_value: int = 0  # Armazenado em centavos para valores fixos


class ProductCreate(Product):
    """Schema para criar um novo produto. Note a ausência de 'variant_ids'."""
    category_id: int
    store_id: int # O store_id virá da URL, mas pode ser útil no corpo

class ProductUpdate(AppBaseModel):
    """Schema para atualizar um produto. Todos os campos são opcionais."""
    name: Optional[str] = None
    description: Optional[str] = None
    base_price: Optional[int] = None
    cost_price: Optional[int] = None
    available: Optional[bool] = None
    promotion_price: Optional[int] = None
    featured: Optional[bool] = None
    activate_promotion: Optional[bool] = None
    ean: Optional[str] = None
    stock_quantity: Optional[int] = None
    control_stock: Optional[bool] = None
    min_stock: Optional[int] = None
    max_stock: Optional[int] = None
    unit: Optional[str] = None
    category_id: Optional[int] = None
    file_key: Optional[str] = Field(default=None, exclude=True)

    cashback_type: Optional[CashbackType] = None
    cashback_value: Optional[int] = None


class ProductDefaultOptionOut(AppBaseModel):
    variant_option_id: int



class ProductOut(Product):
    """
    Schema de resposta da API. É declarativo e poderoso.
    Ele retorna as REGRAS e os complementos aninhados.
    """
    id: int
    category: CategoryOut

    variant_links: List["ProductVariantLinkOut"] = []  # <-- Usar aspas
    components: List[KitComponentOut] = []
    rating: Optional[RatingsSummaryOut] = None
    default_options: List[ProductDefaultOptionOut] = Field(default=[], exclude=True)








    @computed_field
    @property
    def image_path(self) -> str | None:
        """Gera a URL da imagem a partir da file_key."""
        return get_presigned_url(self.file_key) if self.file_key else None


    @computed_field
    @property
    def default_option_ids(self) -> list[int]:
        """
        Extrai apenas os IDs das opções padrão para o frontend consumir facilmente.
        """
        # O 'self' aqui é uma instância do modelo SQLAlchemy 'Product'
        # que o Pydantic está usando para criar o schema.
        # Ele precisa ter o relacionamento 'default_options' carregado.
        if not hasattr(self, 'default_options') or not self.default_options:
            return []

        return [default.variant_option_id for default in self.default_options]


    # ✅ DIFERENCIAL GIGANTE: Estoque calculado para kits
    @computed_field
    @property
    def calculated_stock(self) -> int | None:
        """
        Calcula o estoque real. Se for um produto individual, retorna seu próprio estoque.
        Se for um kit, calcula o estoque com base no componente mais limitado.
        """
        # Se não for um kit, ou se for um kit sem componentes, use o estoque padrão
        if self.product_type != ProductType.KIT or not self.components:
            return self.stock_quantity if self.control_stock else None  # Retorna None para estoque infinito

        possible_kits = []
        for item in self.components:
            # Se algum componente não controla estoque, ele não limita o kit
            if not item.component.control_stock:
                continue

                # Calcula quantos kits podem ser feitos com base neste componente
            stock_for_this_item = item.component.stock_quantity // item.quantity
            possible_kits.append(stock_for_this_item)

        # Se nenhum componente tem estoque controlado, o estoque do kit é "infinito"
        if not possible_kits:
            return None

        # O estoque do kit é o mínimo de kits que podemos montar
        return min(possible_kits)


# -------------------------------------------------
# 2. Schemas de Avaliação (ProductRating)
# -------------------------------------------------

class ProductRatingBase(AppBaseModel):
    rating: int = Field(..., ge=1, le=5)
    comment: Optional[str] = None

class ProductRatingCreate(ProductRatingBase):
    pass

class ProductRatingOut(ProductRatingBase):
    id: int
    product_id: int
    customer_id: int



# É crucial chamar model_rebuild para resolver as referências circulares (ex: KitComponentOut -> ProductOut)
KitComponentOut.model_rebuild()
ProductOut.model_rebuild()