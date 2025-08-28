# schemas/payable/category.py
from pydantic import ConfigDict

from ..base_schema import AppBaseModel


class CategoryResponse(AppBaseModel):
    id: int
    name: str
    model_config = ConfigDict(from_attributes=True)