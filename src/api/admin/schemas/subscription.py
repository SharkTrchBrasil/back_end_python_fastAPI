from datetime import datetime
from pydantic import BaseModel, ConfigDict
from typing import Optional


class SubscriptionPlanFeaturesOut(BaseModel):
    feature_key: str
    is_enabled: bool


class SubscriptionPlanOut(BaseModel):
    id: int
    plan_name: str
    price: int
    interval: int
    repeats: Optional[int] = None
    features: list[SubscriptionPlanFeaturesOut] = []

    model_config = ConfigDict(from_attributes=True)


class StoreSubscriptionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    status: str
    current_period_start: datetime
    current_period_end: datetime
    is_recurring: bool
    plan: SubscriptionPlanOut


# Mantenha suas classes existentes
class Address(BaseModel):
    number: str
    complement: str
    zipcode: str
    city: str
    state: str
    neighborhood: str
    street: str


class Customer(BaseModel):
    name: str
    cpf: str
    email: str
    birth: str
    phone_number: str


class TokenizedCard(BaseModel):
    payment_token: str
    card_mask: str


class CreateStoreSubscription(BaseModel):
    plan_id: int
    address: Address
    customer: Customer
    card: TokenizedCard