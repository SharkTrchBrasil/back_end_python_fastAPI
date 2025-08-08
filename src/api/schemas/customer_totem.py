from pydantic import BaseModel, EmailStr, Field
from typing import List, Optional

class AddressCreate(BaseModel):
    street: str = Field(..., min_length=3)
    number: str
    city_id: Optional[int] = None  # Agora permite None/null
    city_name: str | None = None
    reference: str | None = None
    neighborhood_id: Optional[int] = None # Se neighborhood_id também puder ser nulo
    neighborhood_name: str | None = None
    delivery_scope: str | None = None


class AddressOut(AddressCreate):
    id: int
    model_config = {
        "from_attributes": True  # substitui orm_mode
    }

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