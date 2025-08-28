# schemas/payable/supplier.py
from pydantic import EmailStr, Field, ConfigDict
from typing import Optional

from ..base_schema import AppBaseModel


class SupplierBase(AppBaseModel):
    name: str = Field(..., max_length=255)
    trade_name: Optional[str] = Field(None, max_length=255)
    document: Optional[str] = Field(None, max_length=20)
    email: Optional[EmailStr] = None
    phone: Optional[str] = Field(None, max_length=20)
    address: Optional[dict] = None
    bank_info: Optional[dict] = None
    notes: Optional[str] = None


class SupplierCreate(SupplierBase):
    pass


class SupplierUpdate(SupplierBase):
    name: Optional[str] = None


class SupplierResponse(SupplierBase):
    id: int
    model_config = ConfigDict(from_attributes=True)