from pydantic import BaseModel, EmailStr, Field
from typing import List, Optional

class AddressCreate(BaseModel):
    street: str
    number: Optional[str] = None
    city: str
    reference: Optional[str] = None

    neighborhood_id: Optional[int] = None  # <- se entrega por bairro
    neighborhood_name: Optional[str] = None  # <- se entrega por cidade


class AddressOut(AddressCreate):
    id: int
    class Config:
        orm_mode = True

class CustomerBase(BaseModel):
    name: str
    email: EmailStr
    phone: Optional[str] = None
    photo: Optional[str] = None

class CustomerCreate(CustomerBase):
    addresses: List[AddressCreate] = []

class CustomerOut(CustomerBase):
    id: int
    addresses: List[AddressOut] = []

    class Config:
        orm_mode = True


class CustomerUpdate(BaseModel):
    name: str = Field(..., min_length=2)
    phone: str = Field(..., min_length=8)