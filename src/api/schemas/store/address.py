# schemas/store/address.py
from typing import Optional
from ..base_schema import AppBaseModel


class AddressCreate(AppBaseModel):
    cep: str
    street: str
    number: str
    complement: Optional[str] = None
    neighborhood: str
    city: str
    uf: str


class Address(AppBaseModel):
    number: str
    complement: str
    zipcode: str
    city: str
    state: str
    neighborhood: str
    street: str