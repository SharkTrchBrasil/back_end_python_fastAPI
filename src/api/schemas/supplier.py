from pydantic import BaseModel, EmailStr, Field

# Schema base com campos comuns
class SupplierBase(BaseModel):
    name: str = Field(..., max_length=255)
    trade_name: str | None = Field(None, max_length=255)
    document: str | None = Field(None, max_length=20)
    email: EmailStr | None = None
    phone: str | None = Field(None, max_length=20)
    address: dict | None = None
    bank_info: dict | None = None
    notes: str | None = None

# Schema para criar um fornecedor
class SupplierCreate(SupplierBase):
    pass

# Schema para atualizar um fornecedor
class SupplierUpdate(SupplierBase):
    name: str | None = None # Na atualização, todos os campos são opcionais

# Schema para exibir o fornecedor na resposta da API
class SupplierResponse(SupplierBase):
    id: int

    class Config:
        from_attributes = True # Antigo orm_mode