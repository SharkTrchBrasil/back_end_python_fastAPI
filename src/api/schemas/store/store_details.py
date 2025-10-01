from collections import defaultdict
from typing import Optional, List
from pydantic import Field, ConfigDict, computed_field

from src.api.schemas.chatbot.chatbot_config import StoreChatbotMessageSchema, StoreChatbotConfigSchema
from src.api.schemas.products.category import Category
from src.api.schemas.store.scheduled_pauses import ScheduledPauseOut
from src.api.schemas.subscriptions.store_subscription import StoreSubscriptionSchema


from src.api.schemas.financial.coupon import CouponOut
from src.api.schemas.financial.payment_method import PaymentMethodGroupOut, PlatformPaymentMethodOut

from src.api.schemas.products.product import  ProductOut
from src.api.schemas.products.rating import RatingsSummaryOut
from src.api.schemas.store.store import  StoreSchema
from src.api.schemas.store.location.store_city import StoreCitySchema


from src.api.schemas.store.store_hours import StoreHoursOut
from src.api.schemas.store.store_operation_config import StoreOperationConfigOut

from src.api.schemas.products.variant import Variant


class StoreDetails(StoreSchema):
    # --- Relações que você já tinha ---
    payment_method_groups: list[PaymentMethodGroupOut] = []
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
    # ✅ 2. CORRIJA O NOME DO TIPO AQUI
    scheduled_pauses: list[ScheduledPauseOut] = []

    # ✅ 2. ADICIONE O NOVO CAMPO AQUI
    chatbot_messages: list[StoreChatbotMessageSchema] = []
    # ✅ ADICIONE ESTA LINHA
    chatbot_config: Optional[StoreChatbotConfigSchema] = None

    @computed_field
    @property
    def payment_method_groups(self) -> list[PaymentMethodGroupOut]:
        if not hasattr(self, 'payment_activations'):
            return []

        # Dicionário para agrupar os métodos por seu grupo pai
        groups_map = defaultdict(list)

        for activation in self.payment_activations:
            method = activation.platform_method
            if not method or not method.group:
                continue

            # Anexa os detalhes da ativação da loja ao método
            method_out = PlatformPaymentMethodOut.model_validate(method)
            method_out.activation = activation

            # Agrupa o método completo sob o ID do seu grupo pai
            groups_map[method.group.id].append(method_out)

        # Constrói a lista final de grupos
        result = []

        # Precisamos buscar todos os grupos para ter a lista completa e ordenada
        # É seguro assumir que `self.payment_activations[0].platform_method.group` existe se a lista não for vazia
        # Uma forma mais segura seria ter acesso ao 'db' aqui, mas vamos usar o que temos.
        # Vamos coletar todos os grupos únicos a partir das ativações.
        all_groups = sorted(
            list({act.platform_method.group for act in self.payment_activations if
                  act.platform_method and act.platform_method.group}),
            key=lambda g: g.priority
        )

        for group_model in all_groups:
            group_out = PaymentMethodGroupOut.model_validate(group_model)
            # Pega os métodos já processados do nosso mapa
            group_out.methods = sorted(groups_map.get(group_model.id, []), key=lambda m: m.id)
            result.append(group_out)

        return result

    model_config = ConfigDict(
        from_attributes=True,
        arbitrary_types_allowed=True,
        populate_by_name=True
    )



