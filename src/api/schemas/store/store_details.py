# src/api/schemas/store/store_details.py

from collections import defaultdict
from typing import Optional, List
from pydantic import Field, ConfigDict, computed_field, model_validator

from src.api.admin.services.subscription_service import SubscriptionService
from src.api.schemas.chatbot.chatbot_config import StoreChatbotMessageSchema, StoreChatbotConfigSchema
from src.api.schemas.financial.billing_preview import BillingPreviewSchema
from src.api.schemas.products.category import Category
from src.api.schemas.store.scheduled_pauses import ScheduledPauseOut
from src.api.schemas.financial.coupon import CouponOut
from src.api.schemas.financial.payment_method import PaymentMethodGroupOut, PlatformPaymentMethodOut, StorePaymentMethodActivationOut
from src.api.schemas.products.product import ProductOut
from src.api.schemas.products.rating import RatingsSummaryOut
from src.api.schemas.store.store import StoreSchema
from src.api.schemas.store.location.store_city import StoreCitySchema
from src.api.schemas.store.store_hours import StoreHoursOut
from src.api.schemas.store.store_operation_config import StoreOperationConfigOut
from src.api.schemas.products.variant import Variant
from src.api.schemas.subscriptions.subscription_schemas import SubscriptionDetailsSchema
from src.core import models


class StoreDetails(StoreSchema):
    store_operation_config: StoreOperationConfigOut | None = None
    hours: list[StoreHoursOut] = []
    cities: list[StoreCitySchema] = []
    ratingsSummary: Optional[RatingsSummaryOut] = Field(None, alias="ratingsSummary")
    is_setup_complete: bool
    categories: List[Category] = []
    products: List[ProductOut] = []
    variants: List[Variant] = []
    coupons: List[CouponOut] = []
    scheduled_pauses: list[ScheduledPauseOut] = []
    chatbot_messages: list[StoreChatbotMessageSchema] = []
    chatbot_config: Optional[StoreChatbotConfigSchema] = None
    payment_activations: list[models.StorePaymentMethodActivation] = Field(default=[], exclude=True)
    billing_preview: Optional[BillingPreviewSchema] = Field(default=None)
    active_subscription: SubscriptionDetailsSchema | None

    @model_validator(mode='before')
    @classmethod
    def populate_subscription_details(cls, data):
        """
        Calcula os detalhes da assinatura ANTES do Pydantic criar o modelo.
        """
        if isinstance(data, models.Store):
            # ✅ CALCULA OS DETALHES DA ASSINATURA
            subscription_details_dict = SubscriptionService.get_subscription_details(data)

            # ✅ CONVERTE PARA DICT
            store_dict = {
                key: getattr(data, key)
                for key in cls.model_fields.keys()
                if hasattr(data, key) and key != 'active_subscription'
            }

            # ✅ ADICIONA A ASSINATURA CALCULADA
            store_dict['active_subscription'] = subscription_details_dict

            return store_dict

        return data

    @computed_field(return_type=list[PaymentMethodGroupOut])
    @property
    def payment_method_groups(self) -> list[PaymentMethodGroupOut]:
        """Constrói a estrutura hierárquica de métodos de pagamento."""
        if not self.payment_activations:
            return []

        methods_by_group = defaultdict(list)
        group_models = {}

        for activation in self.payment_activations:
            method_model = activation.platform_method
            if not method_model or not method_model.group:
                continue

            method_out = PlatformPaymentMethodOut.model_validate(method_model)
            method_out.activation = StorePaymentMethodActivationOut.model_validate(activation)
            methods_by_group[method_model.group_id].append(method_out)

            if method_model.group_id not in group_models:
                group_models[method_model.group_id] = method_model.group

        result = []
        sorted_group_ids = sorted(group_models.keys(), key=lambda gid: group_models[gid].priority)

        for group_id in sorted_group_ids:
            group_model = group_models[group_id]
            group_out = PaymentMethodGroupOut.model_validate(group_model)
            methods_for_group = sorted(methods_by_group.get(group_id, []), key=lambda m: m.name)
            group_out.methods = methods_for_group
            result.append(group_out)

        return result

    model_config = ConfigDict(
        from_attributes=True,
        arbitrary_types_allowed=True,
        populate_by_name=True
    )