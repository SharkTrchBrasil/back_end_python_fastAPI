from collections import defaultdict
from typing import Optional, List
from pydantic import Field, ConfigDict, computed_field

from src.api.schemas.chatbot.chatbot_config import StoreChatbotMessageSchema, StoreChatbotConfigSchema
from src.api.schemas.products.category import Category
from src.api.schemas.store.scheduled_pauses import ScheduledPauseOut
from src.api.schemas.subscriptions.store_subscription import StoreSubscriptionSchema
from src.api.schemas.financial.coupon import CouponOut
from src.api.schemas.financial.payment_method import PaymentMethodGroupOut, PlatformPaymentMethodOut
from src.api.schemas.products.product import ProductOut
from src.api.schemas.products.rating import RatingsSummaryOut
from src.api.schemas.store.store import StoreSchema
from src.api.schemas.store.location.store_city import StoreCitySchema
from src.api.schemas.store.store_hours import StoreHoursOut
from src.api.schemas.store.store_operation_config import StoreOperationConfigOut
from src.api.schemas.products.variant import Variant
from src.core import models


class StoreDetails(StoreSchema):
    # --- Relações ---
    # ❌ A LINHA CONFLITANTE FOI REMOVIDA
    # payment_method_groups: list[PaymentMethodGroupOut] = []

    store_operation_config: StoreOperationConfigOut | None = None
    hours: list[StoreHoursOut] = []
    cities: list[StoreCitySchema] = []
    ratingsSummary: Optional[RatingsSummaryOut] = Field(None, alias="ratingsSummary")
    subscription: Optional[StoreSubscriptionSchema] = None
    is_setup_complete: bool
    categories: List[Category] = []
    products: List[ProductOut] = []
    variants: List[Variant] = []
    coupons: List[CouponOut] = []
    scheduled_pauses: list[ScheduledPauseOut] = []
    chatbot_messages: list[StoreChatbotMessageSchema] = []
    chatbot_config: Optional[StoreChatbotConfigSchema] = None

    # ✅ O campo calculado agora é a ÚNICA fonte da verdade para 'payment_method_groups'
    @computed_field(return_type=list[PaymentMethodGroupOut])
    @property
    def payment_method_groups(self) -> list[PaymentMethodGroupOut]:
        """
        Constrói dinamicamente a estrutura hierárquica de grupos de pagamento
        a partir da lista plana de 'payment_activations' carregada do banco.
        """
        # O Pydantic nos dá acesso ao objeto SQLAlchemy original (`self`)
        if not hasattr(self, 'payment_activations'):
            return []

        groups_map = defaultdict(list)

        # Coleta todos os grupos únicos primeiro para manter a ordem de prioridade
        all_groups_from_activations = sorted(
            list({act.platform_method.group for act in self.payment_activations if
                  act.platform_method and act.platform_method.group}),
            key=lambda g: g.priority
        )
        group_model_map = {g.id: g for g in all_groups_from_activations}

        for activation in self.payment_activations:
            method = activation.platform_method
            if not method or not method.group:
                continue

            method_out = PlatformPaymentMethodOut.model_validate(method)
            # Anexa os detalhes da ativação (is_active, is_for_delivery, etc.)
            method_out.activation = models.StorePaymentMethodActivation(**activation.__dict__) if isinstance(activation,
                                                                                                             models.StorePaymentMethodActivation) else activation

            groups_map[method.group_id].append(method_out)

        # Constrói o resultado final na ordem correta
        result = []
        for group_id in group_model_map:
            group_model = group_model_map[group_id]
            group_out = PaymentMethodGroupOut.model_validate(group_model)

            # Pega os métodos já processados e os ordena
            methods_for_group = groups_map.get(group_id, [])
            group_out.methods = sorted(methods_for_group, key=lambda m: m.name)

            result.append(group_out)

        return result

    model_config = ConfigDict(
        from_attributes=True,
        arbitrary_types_allowed=True,
        populate_by_name=True
    )