from datetime import datetime
from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field

from src.api.shared_schemas.product import ProductOut


class DiscountType(str, Enum):
    PERCENTAGE = 'percentage'
    FIXED = 'fixed'


class CouponBase(BaseModel):
    code: str = Field(
        ...,
        min_length=3,
        max_length=20,
        pattern=r'^[A-Z0-9]+$',  # Alterado de 'regex' para 'pattern'
        description="Código do cupom em maiúsculas sem espaços ou caracteres especiais"
    )

    discount_type: DiscountType = Field(default=DiscountType.PERCENTAGE)
    discount_value: int = Field(..., gt=0, description="Valor do desconto em centavos ou percentual")

    # Limites de uso
    max_uses: int | None = Field(None, gt=0, description="Número máximo de usos totais")
    max_uses_per_customer: int | None = Field(
        None, gt=0, alias="maxUsesPerCustomer",
        description="Número máximo de usos por cliente"
    )

    # Validações
    min_order_value: int | None = Field(
        None, gt=0, alias="minOrderValue",
        description="Valor mínimo do pedido em centavos"
    )
    only_for_specific_product: bool = Field(
        default=False,
        description="Se o cupom é válido apenas para um produto específico"
    )

    # Período de validade
    start_date: datetime
    end_date: datetime

    # Restrições
    only_new_customers: bool = Field(
        default=False, alias="onlyNewCustomers",
        description="Se o cupom é válido apenas para novos clientes"
    )
    available: bool = Field(default=True, description="Se o cupom está ativo")

    class Config:
        allow_population_by_field_name = True
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class CouponCreate(CouponBase):
    product_id: int | None = Field(
        None, description="ID do produto específico, se aplicável"
    )


class CouponOut(CouponBase):
    id: int
    used: int = Field(0, description="Número de vezes que o cupom foi usado")
    product: ProductOut | None = None

    @property
    def is_expired(self) -> bool:
        return datetime.now() > self.end_date

    @property
    def is_fully_used(self) -> bool:
        return self.max_uses is not None and self.used >= self.max_uses


class CouponUpdate(BaseModel):
    code: str | None = Field(None, min_length=3, max_length=20)
    discount_type: DiscountType | None = None
    discount_value: int | None = Field(None, gt=0)

    max_uses: int | None = Field(None, gt=0)
    max_uses_per_customer: int | None = Field(None, gt=0, alias="maxUsesPerCustomer")

    min_order_value: int | None = Field(None, gt=0, alias="minOrderValue")
    only_for_specific_product: bool | None = None

    start_date: datetime | None = None
    end_date: datetime | None = None

    only_new_customers: bool | None = Field(None, alias="onlyNewCustomers")
    available: bool | None = None
    product_id: int | None = None

    class Config:
        allow_population_by_field_name = True