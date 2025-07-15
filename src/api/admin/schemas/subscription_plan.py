from pydantic import BaseModel, ConfigDict


class SubscriptionPlan(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    plan_name: str
    price: int
    max_totems: int | None
    style_guide: bool
    interval: int