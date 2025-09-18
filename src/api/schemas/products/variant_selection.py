from pydantic import BaseModel
from typing import List
from pydantic import BaseModel
from typing import List

class VariantSelectionPayload(BaseModel):
    variant_ids: List[int]

# ✅ NOVO SCHEMA ADICIONADO AQUI
class VariantBulkUpdateStatusPayload(BaseModel):
    variant_ids: List[int]
    is_available: bool # True para ativar, False para pausar
