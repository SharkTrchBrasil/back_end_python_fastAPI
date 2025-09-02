from typing import Optional, List
from pydantic import Field, ConfigDict

from src.api.schemas.products.category import Category
from src.api.schemas.store.scheduled_pauses import ScheduledPauseOut
from src.api.schemas.subscriptions.store_subscription import StoreSubscriptionSchema


from src.api.schemas.financial.coupon import CouponOut
from src.api.schemas.financial.payment_method import PaymentMethodGroupOut

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

    model_config = ConfigDict(
        from_attributes=True,
        arbitrary_types_allowed=True,
        populate_by_name=True
    )
