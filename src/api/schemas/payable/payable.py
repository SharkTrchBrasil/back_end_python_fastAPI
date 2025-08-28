# schemas/payable/payable.py
from datetime import date
from pydantic import Field, computed_field, ConfigDict
from typing import Optional

from ..base_schema import AppBaseModel
from .category import CategoryResponse
from .supplier import SupplierResponse


class RecurrenceCreate(AppBaseModel):
    frequency: str = Field(..., description="Ex: 'monthly', 'weekly', 'yearly'")
    interval: int = Field(1, gt=0, description="Ex: a cada 2 meses (frequency='monthly', interval=2)")
    end_date: Optional[date] = Field(None, description="Data final da recorrência, se houver")


class PayableCreate(AppBaseModel):
    title: str = Field(..., max_length=255)
    amount: int = Field(..., gt=0, description="Valor em centavos")
    due_date: date
    description: Optional[str] = None
    category_id: Optional[int] = None
    supplier_id: Optional[int] = None
    barcode: Optional[str] = Field(None, max_length=255)
    notes: Optional[str] = None
    recurrence: Optional[RecurrenceCreate] = None


class PayableUpdate(AppBaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    amount: Optional[int] = None
    due_date: Optional[date] = None
    category_id: Optional[int] = None
    supplier_id: Optional[int] = None


class PayableResponse(AppBaseModel):
    id: int
    title: str
    description: Optional[str] = None
    amount: int
    discount: int
    addition: int
    due_date: date
    payment_date: Optional[date] = None
    status: str
    category: Optional[CategoryResponse] = None
    supplier: Optional[SupplierResponse] = None

    @computed_field
    @property
    def final_amount(self) -> int:
        return self.amount - self.discount + self.addition

    model_config = ConfigDict(from_attributes=True)