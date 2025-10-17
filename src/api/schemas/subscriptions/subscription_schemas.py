# src/api/schemas/subscriptions/subscription_schemas.py

from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, ConfigDict, Field

from .plans import PlanSchema
from .plans_addon import SubscribedAddonSchema
from src.api.schemas.financial.billing_preview import BillingPreviewSchema


class CardInfoSchema(BaseModel):
    """Informações mascaradas do cartão cadastrado"""
    masked_number: str
    brand: str
    status: str
    holder_name: str
    exp_month: int
    exp_year: int

    model_config = ConfigDict(from_attributes=True)


class BillingHistoryItemSchema(BaseModel):
    """Item do histórico de cobranças"""
    period: str
    revenue: float
    fee: float
    status: str
    charge_date: datetime

    model_config = ConfigDict(from_attributes=True)


class SubscriptionDetailsSchema(BaseModel):
    """
    ✅ SCHEMA COMPLETO DA ASSINATURA
    Inclui TODOS os dados necessários para a UI de gerenciamento
    """
    model_config = ConfigDict(from_attributes=True)

    # Campos básicos
    id: int
    current_period_start: datetime
    current_period_end: datetime
    canceled_at: Optional[datetime] = None
    gateway_subscription_id: str | None = None

    # Status calculado
    status: str
    is_blocked: bool
    warning_message: str | None = None
    has_payment_method: bool

    # Relacionamentos
    plan: PlanSchema | None = None
    subscribed_addons: List[SubscribedAddonSchema] = Field(default_factory=list)

    # ✅ DADOS COMPLETOS ADICIONADOS
    billing_preview: BillingPreviewSchema | None = None
    card_info: CardInfoSchema | None = None
    billing_history: List[BillingHistoryItemSchema] = Field(default_factory=list)
    can_cancel: bool = False
    can_reactivate: bool = False