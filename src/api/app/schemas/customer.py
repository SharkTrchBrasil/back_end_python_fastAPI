from pydantic import BaseModel, EmailStr
from typing import List, Optional

class AddressCreate(BaseModel):
    street: str
    city: str
    state: Optional[str] = None
    postal_code: Optional[str] = None

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
