# src/api/schemas/store/table.py
from pydantic import BaseModel, Field
from typing import List, Optional

from src.core.utils.enums import TableStatus


# --- Schemas EXISTENTES (já estavam no seu código) ---

class AddItemToCommandSchema(BaseModel):
    product_id: int
    quantity: int = Field(..., gt=0)
    notes: Optional[str] = None


class CommandItemSchema(BaseModel):
    product_name: str
    quantity: int
    price: int  # Em centavos

    class Config:
        from_attributes = True


class CommandSchema(BaseModel):
    id: int
    customer_name: Optional[str]
    items: List[CommandItemSchema] = []

    class Config:
        from_attributes = True


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


# --- ✅ SCHEMAS NOVOS PARA AS ROTAS ---

# Schemas para Requisições de Mesas
class CreateTableRequest(BaseModel):
    """Schema para criação de uma nova mesa"""
    saloon_id: int = Field(..., gt=0, description="ID do salão onde a mesa será criada")
    name: str = Field(..., min_length=1, max_length=50, description="Nome/número da mesa")
    max_capacity: int = Field(4, gt=0, description="Capacidade máxima de pessoas")
    location_description: Optional[str] = Field(None, max_length=100, description="Descrição da localização")


class UpdateTableRequest(BaseModel):
    """Schema para atualização de uma mesa existente"""
    name: Optional[str] = Field(None, min_length=1, max_length=50)
    max_capacity: Optional[int] = Field(None, gt=0)
    location_description: Optional[str] = Field(None, max_length=100)
    status: Optional[str] = Field(None, description="Status da mesa: AVAILABLE, OCCUPIED, RESERVED")


class OpenTableRequest(BaseModel):
    """Schema para abrir uma mesa (criar comanda)"""
    table_id: int = Field(..., gt=0)
    customer_name: Optional[str] = Field(None, max_length=100, description="Nome do cliente")
    customer_contact: Optional[str] = Field(None, max_length=50, description="Telefone/contato do cliente")
    attendant_id: Optional[int] = Field(None, description="ID do atendente que abriu a mesa")
    notes: Optional[str] = Field(None, max_length=500, description="Observações iniciais")


class CloseTableRequest(BaseModel):
    """Schema para fechar uma mesa"""
    table_id: int = Field(..., gt=0)
    command_id: int = Field(..., gt=0)


# Schemas para Adicionar Itens
class AddItemVariantOption(BaseModel):
    """Representa uma opção de variante selecionada"""
    variant_option_id: int = Field(..., gt=0)
    quantity: int = Field(1, gt=0, description="Quantidade desta opção")


class AddItemVariant(BaseModel):
    """Representa um grupo de variantes (ex: Tamanho, Adicionais)"""
    variant_id: int = Field(..., gt=0)
    options: List[AddItemVariantOption] = Field(default_factory=list)


class AddItemToTableRequest(BaseModel):
    """Schema para adicionar um item ao pedido de uma mesa"""
    table_id: int = Field(..., gt=0, description="ID da mesa")
    command_id: int = Field(..., gt=0, description="ID da comanda ativa")
    product_id: int = Field(..., gt=0, description="ID do produto")
    category_id: int = Field(..., gt=0, description="ID da categoria do produto")
    quantity: int = Field(1, gt=0, description="Quantidade do item")
    note: Optional[str] = Field(None, max_length=500, description="Observações do item")
    variants: List[AddItemVariant] = Field(default_factory=list, description="Variantes/complementos selecionados")


class RemoveItemFromTableRequest(BaseModel):
    """Schema para remover um item do pedido de uma mesa"""
    order_product_id: int = Field(..., gt=0, description="ID do item a ser removido")
    command_id: int = Field(..., gt=0, description="ID da comanda")


# Schemas para Salões
class CreateSaloonRequest(BaseModel):
    """Schema para criar um novo salão/ambiente"""
    name: str = Field(..., min_length=1, max_length=100)
    display_order: int = Field(0, ge=0)


class UpdateSaloonRequest(BaseModel):
    """Schema para atualizar um salão existente"""
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    display_order: Optional[int] = Field(None, ge=0)
    is_active: Optional[bool] = None