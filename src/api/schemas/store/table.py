# src/api/schemas/store/table.py
from pydantic import BaseModel, Field
from typing import List, Optional

from src.core.utils.enums import TableStatus


# --- Schemas para Itens e Comandas (Já existentes e melhorados) ---

class AddItemToCommandSchema(BaseModel):
    product_id: int
    quantity: int = Field(..., gt=0)
    notes: Optional[str] = None
    # variante_options: Optional[List[int]] = [] # Exemplo para o futuro

class CommandItemSchema(BaseModel):
    product_name: str
    quantity: int
    price: int # Em centavos

    class Config:
        from_attributes = True

class CommandSchema(BaseModel):
    id: int
    customer_name: Optional[str]
    items: List[CommandItemSchema] = []

    class Config:
        from_attributes = True

# --- Schemas para Mesas (Tables) ---

class TableBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=50)
    max_capacity: int = Field(4, gt=0)
    location_description: Optional[str] = Field(None, max_length=100)

class TableCreate(TableBase):
    saloon_id: int

class TableUpdate(TableBase):
    name: Optional[str] = Field(None, min_length=1, max_length=50)
    max_capacity: Optional[int] = Field(None, gt=0)

class TableOut(TableBase):
    id: int
    store_id: int
    saloon_id: int
    status: TableStatus
    commands: List[CommandSchema] = []

    class Config:
        from_attributes = True


# --- Schemas para Salões (Saloons) ---

class SaloonBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    display_order: int = 0

class SaloonCreate(SaloonBase):
    pass

class SaloonUpdate(SaloonBase):
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    display_order: Optional[int] = None

class SaloonOut(SaloonBase):
    id: int
    tables: List[TableOut] = []

    class Config:
        from_attributes = True