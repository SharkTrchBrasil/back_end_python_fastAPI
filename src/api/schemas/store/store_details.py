# schemas/store/store_details.py
from typing import Optional, List
from pydantic import Field, ConfigDict

from ..base_schema import AppBaseModel
from .store import StoreSchema
from .store_subscription import StoreSubscriptionSchema
from .store_operation_config import StoreOperationConfigOut
from .store_hours import StoreHoursOut
from .store_city import StoreCitySchema
from ..category.category import CategoryOut
from ..product.product import ProductOut
from ..variant.variant import Variant
from ..rating.rating import RatingsSummaryOut
from ..coupon import CouponOut
from ..payment_method import PaymentMethodGroupOut
from .scheduled_pauses import ScheduledPauseOut


class StoreDetails(StoreSchema):
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
    scheduled_pauses: list[ScheduledPauseOut] = []

    model_config = ConfigDict(
        from_attributes=True,
        arbitrary_types_allowed=True,
        populate_by_name=True
    )