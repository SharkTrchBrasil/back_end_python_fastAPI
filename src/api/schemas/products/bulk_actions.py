# schemas/product/bulk_actions.py
from typing import List
from pydantic import BaseModel, Field

# ✅ 1. Importa a estrutura de dados necessária do arquivo de produto
from .product import ProductPriceInfo


# ✅ 2. Schema para atualizar o status de múltiplos produtos
class BulkStatusUpdatePayload(BaseModel):
    product_ids: List[int]
    available: bool # 'is_active' seria um nome mais consistente com o resto do código


# ✅ 3. Schema para deletar múltiplos produtos
class BulkDeletePayload(BaseModel):
    product_ids: List[int]


# ✅ 4. Schema CORRETO e ÚNICO para mover e reprecificar produtos
class BulkCategoryUpdatePayload(BaseModel):
    target_category_id: int
    products: list[ProductPriceInfo] = Field(..., min_items=1)