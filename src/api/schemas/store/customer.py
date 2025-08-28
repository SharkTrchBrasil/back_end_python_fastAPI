# schemas/store/customer.py
from ..base_schema import AppBaseModel


class Customer(AppBaseModel):
    name: str
    cpf: str
    email: str
    birth: str
    phone_number: str