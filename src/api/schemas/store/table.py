# em schemas/table.py
from pydantic import BaseModel
from typing import List, Optional

# Schema para adicionar um item a uma mesa/comanda
class AddItemToCommandSchema(BaseModel):
    product_id: int
    quantity: int
    notes: Optional[str] = None
    # Adicione aqui os campos para variantes, se necessário
    # variants: List[VariantSchema] 

# Para representar um item dentro de uma comanda
class CommandItemSchema(BaseModel):
    product_name: str
    quantity: int
    price: int

# Para representar uma comanda ativa
class CommandSchema(BaseModel):
    id: int
    customer_name: Optional[str]
    items: List[CommandItemSchema]

# O schema completo de uma mesa para ser enviado via WebSocket/API
class TableOut(BaseModel):
    id: int
    name: str
    status: str
    commands: List[CommandSchema]

    class Config:
        orm_mode = True