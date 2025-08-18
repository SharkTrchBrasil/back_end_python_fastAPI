from typing import Optional, List
from pydantic import Field, ConfigDict

from src.api.schemas.scheduled_pauses import ScheduledPauseOut
from src.api.schemas.store_subscription import StoreSubscriptionSchema
from src.api.schemas.category import CategoryOut

from src.api.schemas.coupon import CouponOut
from src.api.schemas.payment_method import PaymentMethodGroupOut

from src.api.schemas.product import  ProductOut
from src.api.schemas.rating import RatingsSummaryOut
from src.api.schemas.store import  StoreSchema
from src.api.schemas.store_city import StoreCitySchema


from src.api.schemas.store_hours import StoreHoursOut
from src.api.schemas.store_operation_config import StoreOperationConfigOut

from src.api.schemas.variant import Variant


class StoreDetails(StoreSchema):
    # --- Relações que você já tinha ---
    payment_method_groups: list[PaymentMethodGroupOut] = []
    store_operation_config: StoreOperationConfigOut | None = None
    hours: list[StoreHoursOut] = []
    cities: list[StoreCitySchema] = []
    ratingsSummary: Optional[RatingsSummaryOut] = Field(None, alias="ratingsSummary")
    subscription: Optional[StoreSubscriptionSchema] = None
    is_setup_complete: bool
    categories: List[CategoryOut] = []
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
