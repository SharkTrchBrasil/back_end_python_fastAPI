# schemas/variant/variant_selection.py
from pydantic import BaseModel
from typing import List


class VariantSelectionPayload(BaseModel):
    variant_ids: List[int]