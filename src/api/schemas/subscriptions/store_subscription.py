# schemas/store_subscription_schema.py

from datetime import datetime
from pydantic import BaseModel, ConfigDict

from src.api.schemas.subscriptions.plans_addon import SubscribedAddonSchema
from src.api.schemas.subscriptions.plans import PlanSchema


class StoreSubscriptionSchema(BaseModel):
    """Schema completo para a assinatura de uma loja."""
    model_config = ConfigDict(from_attributes=True)

    id: int
    status: str
    current_period_start: datetime
    current_period_end: datetime

    # Aninha o schema do plano para mostrar seus detalhes
    plan: PlanSchema

    # Aninha uma lista com os schemas dos add-ons contratados
    subscribed_addons: list[SubscribedAddonSchema]



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