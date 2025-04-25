from pydantic import BaseModel, computed_field, Field



class Supplier(BaseModel):
    id: int
    name: str
    person_type: str  # 'Física' ou 'Jurídica'
    phone: str
    mobile: str
    cnpj: str
    ie: str
    is_icms_contributor: bool
    is_ie_exempt: bool
    address: str
    email: str
    notes: str
    priority: int