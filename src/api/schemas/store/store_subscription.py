from __future__ import annotations
from typing import TYPE_CHECKING
from datetime import datetime
from pydantic import ConfigDict
from ..base_schema import AppBaseModel
from .address import Address
from .customer import Customer
from .tokenized_card import TokenizedCard

if TYPE_CHECKING:
    from ..plans import PlanSchema
    from ..plans_addon import SubscribedAddonSchema

class StoreSubscriptionSchema(AppBaseModel):
    id: int
    status: str
    current_period_start: datetime
    current_period_end: datetime
    plan: 'PlanSchema'
    subscribed_addons: list['SubscribedAddonSchema']

    model_config = ConfigDict(from_attributes=True)

class CreateStoreSubscription(AppBaseModel):
    plan_id: int
    address: Address
    customer: Customer
    card: TokenizedCard