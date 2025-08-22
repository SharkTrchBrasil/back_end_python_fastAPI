# Em schemas/order.py ou um novo schemas/pagination.py

from pydantic import BaseModel
from typing import List, Generic, TypeVar
from .order import OrderDetails # Supondo que você já tenha um schema para detalhes do pedido

T = TypeVar('T')

class PaginatedResponse(BaseModel, Generic[T]):
    items: List[T]
    total_items: int
    total_pages: int
    page: int
    size: int