# schemas/product/bulk_actions.py
from typing import List
from pydantic import BaseModel


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



class KitComponentOut(BaseModel):
    quantity: int
    # Inclui os dados do produto componente para o front-end saber o que é
    component: "ProductOut"


