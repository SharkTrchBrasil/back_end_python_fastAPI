
from pydantic import BaseModel, ConfigDict, computed_field
from decimal import Decimal
from src.api.schemas.subscriptions.plans_feature import FeatureSchema


class PlanFeatureAssociationSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    feature: FeatureSchema


class PlanSchema(BaseModel):
    """Schema para um plano de assinatura com pricing diferenciado."""
    model_config = ConfigDict(from_attributes=True)

    # --- Campos Básicos do Plano ---
    id: int
    plan_name: str
    available: bool
    support_type: str | None

    # --- NOVA ESTRUTURA DE PREÇOS ---
    minimum_fee: int  # Em centavos
    revenue_percentage: Decimal  # Ex: 0.029 para 2.9%
    revenue_cap_fee: int | None  # Em centavos
    percentage_tier_start: int | None  # Em centavos
    percentage_tier_end: int | None  # Em centavos

    # --- BENEFÍCIOS PROMOCIONAIS ---
    first_month_free: bool
    second_month_discount: Decimal  # Ex: 0.50 para 50%
    third_month_discount: Decimal  # Ex: 0.75 para 25%

    # --- LIMITES DO PLANO ---
    product_limit: int | None
    category_limit: int | None
    user_limit: int | None
    monthly_order_limit: int | None
    location_limit: int | None
    banner_limit: int | None
    max_active_devices: int | None

    # --- Campos de Relacionamento (Features) ---
    included_features: list[PlanFeatureAssociationSchema]

    @computed_field
    @property
    def features(self) -> list[FeatureSchema]:
        """Extrai e achata a lista de features para uma saída mais limpa."""
        return [association.feature for association in self.included_features]