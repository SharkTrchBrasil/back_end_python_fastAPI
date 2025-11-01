"""
Public Menu Schemas - Schemas para API Pública
==============================================
Validação de dados para o cardápio digital público
"""

from pydantic import BaseModel, Field, ConfigDict, validator
from typing import List, Dict, Any, Optional
from datetime import datetime
from decimal import Decimal


# ═══════════════════════════════════════════════════════════
# CARRINHO
# ═══════════════════════════════════════════════════════════

class CartItem(BaseModel):
    """Item do carrinho de compras"""
    
    product_id: int = Field(..., description="ID do produto")
    quantity: int = Field(..., ge=1, le=99, description="Quantidade")
    customizations: Optional[Dict[str, Any]] = Field(
        None,
        description="Customizações selecionadas {group_id: [option_ids]}"
    )
    notes: Optional[str] = Field(None, max_length=500, description="Observações")
    
    model_config = ConfigDict(from_attributes=True)


class CartValidationResponse(BaseModel):
    """Resposta da validação do carrinho"""
    
    valid: bool
    items: List[Dict[str, Any]]
    subtotal: float
    service_fee: float
    total: float
    errors: Optional[List[str]] = None


# ═══════════════════════════════════════════════════════════
# CLIENTE
# ═══════════════════════════════════════════════════════════

class CustomerInfo(BaseModel):
    """Informações do cliente"""
    
    name: str = Field(..., min_length=2, max_length=100, description="Nome completo")
    phone: str = Field(..., pattern=r"^\d{10,11}$", description="Telefone com DDD")
    email: Optional[str] = Field(None, description="Email para contato")
    cpf: Optional[str] = Field(None, pattern=r"^\d{11}$", description="CPF sem formatação")
    
    @validator('phone')
    def validate_phone(cls, v):
        """Remove caracteres não numéricos do telefone"""
        return ''.join(filter(str.isdigit, v))
    
    @validator('cpf')
    def validate_cpf(cls, v):
        """Remove caracteres não numéricos do CPF"""
        if v:
            return ''.join(filter(str.isdigit, v))
        return v


# ═══════════════════════════════════════════════════════════
# PEDIDO
# ═══════════════════════════════════════════════════════════

class CreateOrderRequest(BaseModel):
    """Request para criar pedido"""
    
    store_id: int = Field(..., description="ID da loja")
    items: List[CartItem] = Field(..., min_items=1, description="Itens do pedido")
    customer_info: CustomerInfo = Field(..., description="Dados do cliente")
    notes: Optional[str] = Field(None, max_length=1000, description="Observações gerais")
    schedule_time: Optional[datetime] = Field(None, description="Horário agendado")
    payment_method: Optional[str] = Field(
        "pix",
        pattern="^(pix|credit|debit|cash|voucher)$",
        description="Método de pagamento"
    )
    delivery_address: Optional[Dict[str, Any]] = Field(
        None,
        description="Endereço de entrega (para delivery)"
    )


class OrderResponse(BaseModel):
    """Resposta da criação do pedido"""
    
    success: bool
    order_id: int
    order_number: str
    status: str
    total: float
    preparation_time: int
    estimated_time: datetime
    table: Optional[Dict[str, Any]] = None
    payment_pending: bool
    message: str


class OrderStatusResponse(BaseModel):
    """Resposta do status do pedido"""
    
    order_number: str
    status: str
    status_display: str
    progress: int = Field(..., ge=0, le=100)
    created_at: datetime
    estimated_time: Optional[datetime]
    items: List[Dict[str, Any]]
    total: float
    payment_status: str
    can_cancel: bool
    timeline: List[Dict[str, Any]]


# ═══════════════════════════════════════════════════════════
# CARDÁPIO
# ═══════════════════════════════════════════════════════════

class ProductOption(BaseModel):
    """Opção de customização do produto"""
    
    id: int
    name: str
    description: Optional[str] = None
    price: float
    is_available: bool = True
    tags: List[str] = []


class OptionGroup(BaseModel):
    """Grupo de opções"""
    
    id: int
    name: str
    min_selection: int = 0
    max_selection: int = 1
    required: bool = False
    type: str = "GENERIC"
    options: List[ProductOption]


class ProductBase(BaseModel):
    """Base do produto"""
    
    id: int
    name: str
    description: Optional[str]
    price: float
    original_price: Optional[float] = None
    image: Optional[str] = None
    in_stock: bool = True
    preparation_time: Optional[str] = None
    tags: List[str] = []


class ProductListItem(ProductBase):
    """Item de produto na lista"""
    
    category_name: Optional[str] = None
    discount_percentage: Optional[float] = None


class ProductDetailResponse(ProductBase):
    """Resposta detalhada do produto"""
    
    images: List[str] = []
    category: Optional[Dict[str, Any]] = None
    nutritional_info: Optional[Dict[str, Any]] = None
    allergens: List[str] = []
    rating: Dict[str, Any]
    stock_quantity: Optional[int] = None
    customizations: List[OptionGroup] = []
    size_prices: Optional[List[Dict[str, Any]]] = None
    min_quantity: int = 1
    max_quantity: int = 99


class CategoryResponse(BaseModel):
    """Categoria do cardápio"""
    
    id: int
    name: str
    type: str
    image: Optional[str] = None
    products_count: int
    products: List[ProductListItem]
    option_groups: Optional[List[OptionGroup]] = None
    availability: Dict[str, Any]


class StoreInfo(BaseModel):
    """Informações da loja"""
    
    id: int
    name: str
    logo: Optional[str] = None
    description: Optional[str] = None
    address: str
    phone: Optional[str] = None
    delivery_time: str = "30-45 min"
    minimum_order: float = 0.0
    is_open: bool = True


class MenuResponse(BaseModel):
    """Resposta completa do cardápio"""
    
    store: StoreInfo
    categories: List[CategoryResponse]
    total_products: int
    filters_available: Dict[str, List[Dict[str, Any]]]
    last_updated: datetime


# ═══════════════════════════════════════════════════════════
# PAGAMENTO
# ═══════════════════════════════════════════════════════════

class PaymentRequest(BaseModel):
    """Request para criar pagamento"""
    
    order_id: int
    payment_method: str = Field(
        ...,
        pattern="^(pix|credit|debit|cash|voucher)$"
    )
    installments: Optional[int] = Field(None, ge=1, le=12)
    customer_document: Optional[str] = Field(None, description="CPF/CNPJ")


class PaymentResponse(BaseModel):
    """Resposta do pagamento"""
    
    payment_id: Optional[str] = None
    payment_method: str
    status: str = "pending"
    qr_code: Optional[str] = None
    qr_code_base64: Optional[str] = None
    payment_url: Optional[str] = None
    barcode: Optional[str] = None
    total: float
    expires_at: Optional[datetime] = None
    message: Optional[str] = None


# ═══════════════════════════════════════════════════════════
# AVALIAÇÃO
# ═══════════════════════════════════════════════════════════

class RatingRequest(BaseModel):
    """Request para avaliar pedido"""
    
    order_id: int
    rating: int = Field(..., ge=1, le=5, description="Nota de 1 a 5")
    comment: Optional[str] = Field(None, max_length=500)
    recommend: Optional[bool] = Field(None, description="Recomendaria?")


class RatingResponse(BaseModel):
    """Resposta da avaliação"""
    
    success: bool
    message: str
    rating_id: Optional[int] = None


# ═══════════════════════════════════════════════════════════
# GARÇOM
# ═══════════════════════════════════════════════════════════

class CallWaiterRequest(BaseModel):
    """Request para chamar garçom"""
    
    table_id: int
    reason: Optional[str] = Field(
        None,
        max_length=200,
        description="Motivo da chamada"
    )
    urgency: str = Field(
        "normal",
        pattern="^(low|normal|high|urgent)$"
    )


class CallWaiterResponse(BaseModel):
    """Resposta da chamada do garçom"""
    
    success: bool
    message: str
    call_id: int
    estimated_time: Optional[str] = None


# ═══════════════════════════════════════════════════════════
# QR CODE
# ═══════════════════════════════════════════════════════════

class QRValidationResponse(BaseModel):
    """Resposta da validação do QR code"""
    
    valid: bool
    store: StoreInfo
    table: Optional[Dict[str, Any]] = None
    active_command: Optional[Dict[str, Any]] = None
    message: Optional[str] = None
