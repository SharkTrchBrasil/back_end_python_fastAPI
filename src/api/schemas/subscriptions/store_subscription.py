"""
Schemas para assinatura de lojas
=================================
Define os modelos de dados para criação e gerenciamento de assinaturas.
"""

from pydantic import BaseModel, Field, field_validator
import re


class TokenizedCard(BaseModel):
    """
    Token de cartão gerado pelo frontend via Pagar.me.

    O frontend tokeniza o cartão usando a Public Key e envia
    apenas o token (sem expor dados sensíveis do cartão).
    """
    payment_token: str = Field(
        ...,
        min_length=10,
        description="Token gerado pelo Pagar.me (ex: tok_abc123xyz)",
        examples=["tok_RmOzMDwILkSdgxVp"]
    )

    card_mask: str = Field(
        ...,
        min_length=16,
        max_length=19,
        description="Máscara do cartão no formato ************1234",
        examples=["************1234", "**** **** **** 1234"]
    )

    @field_validator('card_mask')
    @classmethod
    def validate_card_mask(cls, v: str) -> str:
        """
        Valida se a máscara do cartão está no formato correto.

        Aceita:
        - ************1234 (sem espaços)
        - **** **** **** 1234 (com espaços)
        """
        # Remove espaços para validação
        clean = v.replace(' ', '')

        # Deve ter exatamente 16 caracteres (12 asteriscos + 4 números)
        if not re.match(r'^\*{12}\d{4}$', clean):
            raise ValueError(
                'Máscara do cartão deve estar no formato ************1234 '
                'ou **** **** **** 1234'
            )

        return v

    @field_validator('payment_token')
    @classmethod
    def validate_payment_token(cls, v: str) -> str:
        """Valida que o token não está vazio e tem tamanho mínimo"""
        if not v or len(v.strip()) < 10:
            raise ValueError('Token de pagamento inválido')
        return v.strip()


class CreateStoreSubscription(BaseModel):
    """
    ✅ Payload minimalista e profissional para criação de assinatura.

    O frontend envia APENAS o token do cartão.
    Todos os outros dados (cliente, endereço) são obtidos da loja
    no backend (Single Source of Truth).

    Benefícios:
    - Payload mínimo (performance)
    - Dados sempre atualizados
    - Validação centralizada no backend
    - Menos código no frontend
    """
    card: TokenizedCard = Field(
        ...,
        description="Dados tokenizados do cartão de crédito"
    )

    class Config:
        from_attributes = True
        json_schema_extra = {
            "example": {
                "card": {
                    "payment_token": "tok_RmOzMDwILkSdgxVp",
                    "card_mask": "************1234"
                }
            }
        }