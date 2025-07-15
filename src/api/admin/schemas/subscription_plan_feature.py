from pydantic import BaseModel, ConfigDict

class SubscriptionPlanFeature(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    feature_key: str
    is_enabled: bool
