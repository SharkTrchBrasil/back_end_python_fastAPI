from datetime import datetime
from enum import Enum
from pydantic import BaseModel, Field, field_serializer
from typing import Optional

from src.api.shared_schemas.product import ProductOut


class DiscountType(str, Enum):
    PERCENTAGE = 'percentage'
    FIXED = 'fixed'


class CouponBase(BaseModel):
    code: str = Field(
        ..., min_length=3, max_length=20,
        pattern=r'^[A-Z0-9]+$',
        description="Código do cupom em maiúsculas sem espaços ou caracteres especiais"
    )
    discount_type: DiscountType = Field(default=DiscountType.PERCENTAGE)
    discount_value: int = Field(..., gt=0, description="Valor do desconto em centavos ou percentual")

    max_uses: Optional[int] = Field(None, gt=0, description="Número máximo de usos totais")
    max_uses_per_customer: Optional[int] = Field(None, gt=0, alias="maxUsesPerCustomer",
                                                description="Número máximo de usos por cliente")
    min_order_value: Optional[int] = Field(None, gt=0, alias="minOrderValue",
                                           description="Valor mínimo do pedido em centavos")

    start_date: datetime
    end_date: datetime

    only_new_customers: bool = Field(default=False, alias="onlyNewCustomers",
                                    description="Se o cupom é válido apenas para novos clientes")

    is_active: bool = Field(default=True, description="Se o cupom está ativo")

    @field_serializer('start_date', 'end_date')
    def serialize_datetime(self, value: datetime | None) -> str | None:
        return value.isoformat() if value else None

    class Config:
        json_encoders = {datetime: lambda v: v.isoformat()}
        from_attributes = True  # Para suportar ORM
class CouponCreate(CouponBase):
    product_id: Optional[int] = Field(None, description="ID do produto específico, se aplicável")


class CouponOut(CouponBase):
    id: int
    used: int = Field(0, description="Número de vezes que o cupom foi usado")
    product: Optional[ProductOut] = None



    class Config:
        from_attributes = True  # ✅ Isso permite aceitar ORM direto



    @property
    def is_expired(self) -> bool:
        return datetime.now() > self.end_date

    @property
    def is_fully_used(self) -> bool:
        return self.max_uses is not None and self.used >= self.max_uses


class CouponUpdate(BaseModel):
    code: Optional[str] = Field(None, min_length=3, max_length=20)
    discount_type: Optional[DiscountType] = None
    discount_value: Optional[int] = Field(None, gt=0)

    max_uses: Optional[int] = Field(None, gt=0)
    max_uses_per_customer: Optional[int] = Field(None, gt=0, alias="maxUsesPerCustomer")
    min_order_value: Optional[int] = Field(None, gt=0, alias="minOrderValue")

    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None

    only_new_customers: Optional[bool] = Field(None, alias="onlyNewCustomers")
    is_active: Optional[bool] = None
    product_id: Optional[int] = None
