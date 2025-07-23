# schemas/store_subscription_schema.py

from datetime import datetime
from pydantic import BaseModel, ConfigDict

from src.api.admin.schemas.plans_addon import SubscribedAddonSchema
from src.api.admin.schemas.plans import SubscriptionPlanSchema


class StoreSubscriptionSchema(BaseModel):
    """Schema completo para a assinatura de uma loja."""
    model_config = ConfigDict(from_attributes=True)

    id: int
    status: str
    current_period_start: datetime
    current_period_end: datetime

    # Aninha o schema do plano para mostrar seus detalhes
    plan: SubscriptionPlanSchema

    # Aninha uma lista com os schemas dos add-ons contratados
    subscribed_addons: list[SubscribedAddonSchema]