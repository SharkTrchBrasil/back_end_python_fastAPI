from pydantic import BaseModel, EmailStr, Field
from typing import List, Optional


class AddressCreate(BaseModel):
    """Schema base com os campos comuns de um endereço, com validações."""
    label: str = Field(..., max_length=50, description="Um rótulo para o endereço, ex: 'Casa', 'Trabalho'")
    zip_code: str = Field(..., max_length=9, description="CEP, ex: '12345-678'")
    street: str = Field(..., max_length=200)
    number: str = Field(..., max_length=50)
    complement: Optional[str] = Field(None, max_length=100)
    neighborhood: str = Field(..., max_length=100)
    city: str = Field(..., max_length=100)
    state: str = Field(..., min_length=2, max_length=2, description="UF do estado, ex: 'SP'")
    reference: Optional[str] = Field(None, max_length=150)
    is_favorite: bool = Field(default=False)
    city_id: int
    neighborhood_id: int


class AddressOut(AddressCreate):
    id: int
    # ✅ ELES ESTÃO AQUI!
    city_id: Optional[int] = None
    neighborhood_id: Optional[int] = None

    class ConfigDict:
        from_attributes = True


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