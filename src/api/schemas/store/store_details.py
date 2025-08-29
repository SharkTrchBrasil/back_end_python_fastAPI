# ✅ SUBSTITUA o arquivo INTEIRO por este código:

from typing import Optional, List
from pydantic import Field, ConfigDict

from src.api.schemas.base_schema import AppBaseModel
from src.api.schemas.store.store import StoreSchema
from src.api.schemas.store.store_subscription import StoreSubscriptionSchema
from src.api.schemas.store.store_operation_config import StoreOperationConfigOut
from src.api.schemas.store.store_hours import StoreHoursOut
from src.api.schemas.store.store_city import StoreCitySchema

# IMPORTE DIRETAMENTE (não use TYPE_CHECKING):
from src.api.schemas.payment_method import PaymentMethodGroupOut
from src.api.schemas.rating import RatingsSummaryOut
from src.api.schemas.category import CategoryOut
from src.api.schemas.product.product import ProductOut
from src.api.schemas.variant.variant import Variant
from src.api.schemas.coupon import CouponOut
from src.api.schemas.store.scheduled_pauses import ScheduledPauseOut

class StoreDetails(StoreSchema):
    payment_method_groups: list[PaymentMethodGroupOut] = []
    store_operation_config: Optional[StoreOperationConfigOut] = None
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