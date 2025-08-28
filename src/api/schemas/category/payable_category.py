# schemas/category/payable_category.py
from pydantic import Field

from ..base_schema import AppBaseModel


class PayableCategoryBase(AppBaseModel):
    name: str = Field(..., min_length=2, max_length=100)


class PayableCategoryCreate(PayableCategoryBase):
    pass


class PayableCategoryUpdate(PayableCategoryBase):
    pass


class PayableCategoryResponse(PayableCategoryBase):
    id: int