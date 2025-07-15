from typing import List
from pydantic import BaseModel, ConfigDict
from src.api.admin.schemas.subscription_plan_feature import SubscriptionPlanFeature

class SubscriptionPlan(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    plan_name: str
    price: int
    interval: int
    features: List[SubscriptionPlanFeature] = []