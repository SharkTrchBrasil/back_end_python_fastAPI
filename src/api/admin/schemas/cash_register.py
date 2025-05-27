# SEUS SCHEMAS:
from pydantic import BaseModel, Field
from decimal import Decimal # Se você usa Decimal, mantenha
from typing import Optional
from datetime import datetime

# --- Schema Base para Campos Comuns de Criação/Atualização ---
# Este schema define os campos que o frontend envia para criar ou atualizar um CashRegister
class CashRegisterCreateUpdateBase(BaseModel):
    initial_balance: float = Field(..., gt=0)# O campo 'initial_balance' deve vir no body
    is_active: bool = True

# --- Schema para Criação de CashRegister ---
# Herda os campos de criação/atualização
class CashRegisterCreate(CashRegisterCreateUpdateBase):
    pass # Não precisa de campos adicionais se CashRegisterCreateUpdateBase já tiver tudo


# --- Schema para Saída (o que o backend retorna) ---
# Este schema define todos os campos que o backend *retorna* sobre um CashRegister
class CashRegisterOut(BaseModel): # Use BaseModel diretamente ou herde de um Base genérico se tiver
    id: int
    store_id: int # Retornado pelo backend
    opened_at: datetime
    closed_at: Optional[datetime] = None # Pode ser nulo
    initial_balance: float
    current_balance: float
    is_active: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True # Antigo orm_mode = True no Pydantic v2