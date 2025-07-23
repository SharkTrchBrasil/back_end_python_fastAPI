# schemas/subscription_plan_schema.py

from pydantic import BaseModel, ConfigDict, computed_field

from src.api.admin.schemas.plans_feature import FeatureSchema


# Este schema intermediário nos ajuda a extrair a feature da associação
class _SubscriptionPlanFeatureAssociationSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    feature: FeatureSchema


class SubscriptionPlanSchema(BaseModel):
    """Schema para um plano de assinatura, mostrando as features inclusas."""
    model_config = ConfigDict(from_attributes=True)

    id: int
    plan_name: str
    price: int
    interval: int
    available: bool

    # Campo "real" que vem do SQLAlchemy
    included_features: list[_SubscriptionPlanFeatureAssociationSchema]

    # ✨ Campo "virtual" que criamos para deixar a API mais limpa
    @computed_field
    @property
    def features(self) -> list[FeatureSchema]:
        """Extrai e achata a lista de features para uma saída mais limpa."""
        return [association.feature for association in self.included_features]