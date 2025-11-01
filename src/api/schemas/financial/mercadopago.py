"""
Schemas para Mercado Pago
=========================
Define os modelos de dados para integração com Mercado Pago
"""

from pydantic import BaseModel, Field, field_validator
from typing import Optional, Dict
from datetime import datetime


class MercadoPagoConfigSchema(BaseModel):
    """Configuração de conexão do Mercado Pago para uma loja"""

    is_connected: bool = Field(default=False, description="Se a loja está conectada ao MP")
    access_token_encrypted: Optional[str] = Field(None, description="Access token criptografado")
    public_key: Optional[str] = Field(None, description="Public key do lojista")
    user_id: Optional[str] = Field(None, description="ID do usuário no Mercado Pago")
    connected_at: Optional[datetime] = Field(None, description="Data da conexão")
    last_sync_at: Optional[datetime] = Field(None, description="Última sincronização")

    class Config:
        from_attributes = True


class MercadoPagoConnectRequest(BaseModel):
    """Request para conectar loja ao Mercado Pago"""

    access_token: str = Field(..., description="Access token do Mercado Pago")
    public_key: str = Field(..., description="Public key do Mercado Pago")

    @field_validator('access_token')
    @classmethod
    def validate_access_token(cls, v: str) -> str:
        if not v or len(v.strip()) < 10:
            raise ValueError('Access token inválido')
        if not v.startswith('APP_USR-') and not v.startswith('TEST-'):
            raise ValueError('Access token deve começar com APP_USR- ou TEST-')
        return v.strip()

    @field_validator('public_key')
    @classmethod
    def validate_public_key(cls, v: str) -> str:
        if not v or len(v.strip()) < 10:
            raise ValueError('Public key inválida')
        return v.strip()


class MercadoPagoPaymentRequest(BaseModel):
    """Request para criar pagamento via Mercado Pago"""

    amount: float = Field(..., gt=0, description="Valor em R$")
    description: str = Field(..., max_length=200)
    payer_email: str = Field(..., description="Email do pagador")

    # PIX específico
    payer_first_name: str = Field(..., max_length=50)
    payer_last_name: str = Field(..., max_length=50)
    payer_document_type: str = Field(default="CPF", description="CPF ou CNPJ")
    payer_document_number: str = Field(..., description="Documento sem formatação")

    metadata: Optional[Dict] = Field(None, description="Metadados adicionais")

    @field_validator('payer_email')
    @classmethod
    def validate_email(cls, v: str) -> str:
        if '@' not in v:
            raise ValueError('Email inválido')
        return v.strip().lower()

    @field_validator('payer_document_type')
    @classmethod
    def validate_document_type(cls, v: str) -> str:
        if v.upper() not in ['CPF', 'CNPJ']:
            raise ValueError('Tipo de documento deve ser CPF ou CNPJ')
        return v.upper()

    @field_validator('payer_document_number')
    @classmethod
    def validate_document_number(cls, v: str, info) -> str:
        # Remove formatação
        clean = ''.join(filter(str.isdigit, v))
        
        # Valida conforme tipo
        doc_type = info.data.get('payer_document_type', 'CPF')
        if doc_type == 'CPF' and len(clean) != 11:
            raise ValueError('CPF deve ter 11 dígitos')
        if doc_type == 'CNPJ' and len(clean) != 14:
            raise ValueError('CNPJ deve ter 14 dígitos')
        
        return clean

    class Config:
        json_schema_extra = {
            "example": {
                "amount": 50.00,
                "description": "Pedido #1234",
                "payer_email": "cliente@example.com",
                "payer_first_name": "João",
                "payer_last_name": "Silva",
                "payer_document_type": "CPF",
                "payer_document_number": "12345678900",
                "metadata": {
                    "order_id": "1234",
                    "store_id": "1"
                }
            }
        }


class MercadoPagoPaymentResponse(BaseModel):
    """Response de pagamento criado no Mercado Pago"""

    payment_id: str = Field(..., description="ID do pagamento no MP")
    status: str = Field(..., description="Status do pagamento")
    status_detail: Optional[str] = Field(None, description="Detalhes do status")

    # PIX específico
    qr_code_base64: Optional[str] = Field(None, description="QR code PIX em base64")
    qr_code: Optional[str] = Field(None, description="Código PIX copia e cola")
    ticket_url: Optional[str] = Field(None, description="URL do ticket/boleto")

    transaction_amount: float = Field(..., description="Valor da transação")
    created_at: datetime = Field(..., description="Data de criação")

    payer: Optional[Dict] = Field(None, description="Dados do pagador")
    point_of_interaction: Optional[Dict] = Field(None, description="Dados do PIX")

    class Config:
        from_attributes = True


class MercadoPagoWebhookPayload(BaseModel):
    """Payload do webhook do Mercado Pago"""

    action: str = Field(..., description="Ação: payment.created, payment.updated, etc")
    type: str = Field(..., description="Tipo: payment")
    data_id: str = Field(..., alias="data.id", description="ID do recurso")
    date_created: datetime = Field(..., description="Data do evento")
    user_id: Optional[str] = Field(None, description="ID do usuário")

    class Config:
        populate_by_name = True
        from_attributes = True


class MercadoPagoRefundRequest(BaseModel):
    """Request para reembolso"""

    amount: Optional[float] = Field(None, gt=0, description="Valor a reembolsar (None = total)")

    class Config:
        json_schema_extra = {
            "example": {
                "amount": 25.00  # Reembolso parcial
            }
        }



