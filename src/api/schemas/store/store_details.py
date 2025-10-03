from collections import defaultdict
from typing import Optional, List
from pydantic import Field, ConfigDict, computed_field, model_validator

from src.api.admin.services.subscription_service import SubscriptionService
from src.api.schemas.chatbot.chatbot_config import StoreChatbotMessageSchema, StoreChatbotConfigSchema
from src.api.schemas.financial.billing_preview import BillingPreviewSchema
from src.api.schemas.products.category import Category
from src.api.schemas.store.scheduled_pauses import ScheduledPauseOut
from src.api.schemas.subscriptions.store_subscription import StoreSubscriptionSchema
from src.api.schemas.financial.coupon import CouponOut
# ✅ Importe os schemas corretos
from src.api.schemas.financial.payment_method import PaymentMethodGroupOut, PlatformPaymentMethodOut, \
    StorePaymentMethodActivationOut
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

    # ✅ 2. Adicione o campo para o preview do faturamento
    billing_preview: Optional[BillingPreviewSchema] = Field(default=None)

    # ✅ O CAMPO CRUCIAL
    # Este campo não vem diretamente do banco, ele será populado pelo nosso serviço.
    active_subscription: SubscriptionDetailsSchema | None

    class Config:
        from_attributes = True

    # ✅ A MÁGICA ACONTECE AQUI
    # Este validador intercepta a criação do schema e popula o campo 'active_subscription'
    @model_validator(mode='before')
    @classmethod
    def populate_subscription_details(cls, data):
        if isinstance(data, models.Store):
            # 'data' é o objeto ORM da loja.
            # Chamamos nosso serviço para obter os detalhes calculados.
            subscription_details = SubscriptionService.get_subscription_details(data)

            # Adicionamos os detalhes calculados ao dicionário de dados
            # que será usado para criar o StoreSchema.
            data.active_subscription = subscription_details
        return data




    @computed_field(return_type=list[PaymentMethodGroupOut])
    @property
    def payment_method_groups(self) -> list[PaymentMethodGroupOut]:
        """
        Constrói dinamicamente a estrutura hierárquica de grupos de pagamento
        a partir da lista 'payment_activations' carregada do banco.
        """
        if not self.payment_activations:
            return []

        methods_by_group = defaultdict(list)
        group_models = {}


        for activation in self.payment_activations:
            method_model = activation.platform_method
            if not method_model or not method_model.group:
                continue

            # Converte o método do SQLAlchemy para o schema Pydantic
            method_out = PlatformPaymentMethodOut.model_validate(method_model)
            # Anexa os detalhes da ativação (convertidos para schema) ao método
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