# schemas/store/responsible.py
from ..base_schema import AppBaseModel


class ResponsibleCreate(AppBaseModel):
    name: str
    phone: str