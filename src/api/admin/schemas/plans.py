# schemas/subscription_plan_schema.py

from pydantic import BaseModel, ConfigDict, computed_field
from src.api.admin.schemas.plans_feature import FeatureSchema


# Este schema intermediário nos ajuda a extrair a feature da associação
class PlanFeatureAssociationSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    feature: FeatureSchema


class PlanSchema(BaseModel):
    """Schema para um plano de assinatura, mostrando as features e limites inclusos."""
    model_config = ConfigDict(from_attributes=True)

    # --- Campos Básicos do Plano ---
    id: int
    plan_name: str
    price: int
    interval: int
    repeats: int | None
    available: bool

    # --- NOVOS CAMPOS: Limites e Benefícios ---
    # Adicionamos todos os novos campos que estão na tabela do banco de dados.
    # O tipo 'int | None' permite que o valor seja um número ou nulo (ilimitado).
    product_limit: int | None
    category_limit: int | None
    user_limit: int | None
    monthly_order_limit: int | None
    location_limit: int | None
    banner_limit: int | None
    max_active_devices: int | None
    support_type: str | None

    # --- Campos de Relacionamento (Features) ---

    # Campo "real" que vem do SQLAlchemy
    included_features: list[PlanFeatureAssociationSchema]

    # ✨ Campo "virtual" que criamos para deixar a API mais limpa
    @computed_field
    @property
    def features(self) -> list[FeatureSchema]:
        """Extrai e achata la lista de features para uma saída mais limpa."""
        return [association.feature for association in self.included_features]
