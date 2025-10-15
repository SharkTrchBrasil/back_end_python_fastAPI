# src/api/schemas/store/table.py
from datetime import datetime

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


class CommandOut(BaseModel):
    id: int
    store_id: int
    table_id: Optional[int] = None
    customer_name: Optional[str] = None
    customer_contact: Optional[str] = None
    status: str
    attendant_id: Optional[int] = None
    notes: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    # Campos calculados
    table_name: Optional[str] = None
    total_amount: int = 0  # Em centavos

    # ✅ NOVO: Lista de itens da comanda
    items: List['CommandItemOut'] = []

    class Config:
        from_attributes = True

    @classmethod
    def from_orm_with_totals(cls, command):
        """Factory method para criar CommandOut com cálculos e itens"""

        # Calcula o total e monta os itens
        total = 0
        items = []

        if hasattr(command, 'orders') and command.orders:
            for order in command.orders:
                total += order.discounted_total_price or order.total_price

                # ✅ Adiciona os produtos de cada pedido
                for product in order.products:
                    items.append({
                        'order_id': order.id,
                        'product_id': product.product_id,
                        'product_name': product.name,
                        'quantity': product.quantity,
                        'price': product.price,
                        'note': product.note,
                        'image_url': product.image_url,
                    })

        table_name = command.table.name if command.table else None
        status_str = command.status.value if hasattr(command.status, 'value') else str(command.status)

        return cls(
            id=command.id,
            store_id=command.store_id,
            table_id=command.table_id,
            customer_name=command.customer_name,
            customer_contact=command.customer_contact,
            status=status_str,
            attendant_id=command.attendant_id,
            notes=command.notes,
            created_at=command.created_at.isoformat() if command.created_at else None,
            updated_at=command.updated_at.isoformat() if command.updated_at else None,
            table_name=table_name,
            total_amount=total,
            items=items,  # ✅ Inclui os itens
        )


# ✅ NOVO: Schema para os itens da comanda
class CommandItemOut(BaseModel):
    order_id: int
    product_id: int
    product_name: str
    quantity: int
    price: int  # Em centavos
    note: Optional[str] = None
    image_url: Optional[str] = None

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
    table_id: Optional[int] = Field(None, gt=0, description="ID da mesa (opcional para comandas avulsas)")  # ✅ MUDOU
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