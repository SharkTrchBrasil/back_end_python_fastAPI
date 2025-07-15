from pydantic import BaseModel, ConfigDict

from src.api.admin.schemas.subscription_plan import SubscriptionPlan


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


class StoreSubscription(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    plan: SubscriptionPlan