# src/api/schemas/subscriptions/subscription_schemas.py

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict
from .plans import PlanSchema
from .plans_addon import SubscribedAddonSchema

class SubscriptionDetailsSchema(BaseModel):
    """
    Schema para os detalhes CALCULADOS da assinatura.
    Esta é a estrutura que o frontend deve consumir.
    """
    model_config = ConfigDict(from_attributes=True)

    # Campos da assinatura original
    id: int
    current_period_start: datetime
    current_period_end: datetime
    gateway_subscription_id: str | None
    status: str  # ✅ Aceita: active, trialing, canceled, expired, past_due
    canceled_at: Optional[datetime] = None  # ✅ ADICIONA CAMPO
    # Campos calculados pelo SubscriptionService
    status: str  # O status dinâmico (active, trialing, warning, past_due, etc.)
    is_blocked: bool  # A fonte da verdade para bloqueio de UI
    warning_message: str | None  # A mensagem a ser exibida
    # ✅ NOVO CAMPO BOOLEANO
    has_payment_method: bool  # ← SIMPLES E DIRETO!
    # Relações aninhadas
    plan: PlanSchema | None
    subscribed_addons: list[SubscribedAddonSchema]