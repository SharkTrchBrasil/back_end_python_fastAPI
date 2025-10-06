from datetime import datetime
from pydantic import BaseModel, Field, field_serializer
from typing import Optional, Any


# ===================================================================
# ✅ NOVO: Schema para representar as REGRAS
# ===================================================================
class CouponRuleSchema(BaseModel):
    # 'MIN_SUBTOTAL', 'FIRST_ORDER', 'TARGET_PRODUCT', 'TARGET_CATEGORY', 'MAX_USES_TOTAL', 'MAX_USES_PER_CUSTOMER'
    rule_type: str = Field(..., alias="ruleType")

    # Dicionário flexível para os valores da regra. Ex: {"value": 5000} ou {"product_id": 123}
    value: dict[str, Any]

    class Config:
        from_attributes = True
        populate_by_name = True  # Permite usar tanto 'rule_type' quanto 'ruleType'


# ===================================================================
# Schema Base do Cupom (Refatorado)
# ===================================================================
class CouponBase(BaseModel):
    code: str = Field(
        ..., min_length=3, max_length=50,
        pattern=r'^[A-Z0-9]+$',
        description="Código do cupom em maiúsculas sem espaços ou caracteres especiais"
    )
    description: Optional[str] = Field(None, min_length=3, max_length=255)

    # A AÇÃO do cupom
    discount_type: str = Field(..., alias="discountType")  # 'PERCENTAGE', 'FIXED_AMOUNT', 'FREE_DELIVERY'
    discount_value: float = Field(..., gt=0, alias="discountValue")

    max_discount_amount: Optional[int] = Field(None, gt=0, alias="maxDiscountAmount",
                                               description="Teto do desconto em centavos para %")

    # Validade
    # ✅✅✅ CORREÇÃO APLICADA AQUI ✅✅✅
    # Adicionados os aliases que faltavam para corresponder ao frontend.
    start_date: datetime = Field(..., alias="startDate")
    end_date: datetime = Field(..., alias="endDate")
    is_active: bool = Field(default=True, alias="isActive")

    class Config:
        from_attributes = True
        populate_by_name = True  # Essencial para os aliases funcionarem
        json_encoders = {datetime: lambda v: v.isoformat()}


# ===================================================================
# Schemas para Criar e Atualizar
# ===================================================================
class CouponCreate(CouponBase):
    # Agora, em vez de campos de regra individuais, recebemos uma lista de regras
    rules: list[CouponRuleSchema] = []


class CouponUpdate(BaseModel):
    # Todos os campos são opcionais na atualização
    code: Optional[str] = Field(None, min_length=3, max_length=50, pattern=r'^[A-Z0-9]+$')
    description: Optional[str] = Field(None, min_length=3, max_length=255)
    discount_type: Optional[str] = Field(None, alias="discountType")
    discount_value: Optional[float] = Field(None, gt=0, alias="discountValue")
    max_discount_amount: Optional[int] = Field(None, gt=0, alias="maxDiscountAmount")
    start_date: Optional[datetime] = Field(None, alias="startDate")
    end_date: Optional[datetime] = Field(None, alias="endDate")
    is_active: Optional[bool] = Field(None, alias="isActive")
    rules: Optional[list[CouponRuleSchema]] = None


# ===================================================================
# Schema para Exibir (Saída da API)
# ===================================================================
class CouponOut(CouponBase):
    id: int
    rules: list[CouponRuleSchema] = []  # Exibe as regras associadas ao cupom

    # Opcional: Contar e exibir o número de usos
    # total_usages: int = Field(0, alias="totalUsages")

    @field_serializer('start_date', 'end_date')
    def serialize_datetime(self, value: datetime | None) -> str | None:
        return value.isoformat() if value else None