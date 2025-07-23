# schemas/subscribed_addon_schema.py

from datetime import datetime
from pydantic import BaseModel, ConfigDict

from src.api.admin.schemas.plans_feature import FeatureSchema


class SubscribedAddonSchema(BaseModel):
    """Schema para um add-on contratado em uma assinatura."""
    model_config = ConfigDict(from_attributes=True)

    id: int
    price_at_subscription: int
    subscribed_at: datetime

    # Aninha o schema da feature para mostrar todos os seus detalhes
    feature: FeatureSchema