from typing import Optional, List
from pydantic import Field, ConfigDict


from src.api.admin.schemas.store_subscription import StoreSubscriptionSchema
from src.api.shared_schemas.category import CategoryOut

from src.api.shared_schemas.coupon import CouponOut
from src.api.shared_schemas.payment_method import PaymentMethodGroupOut

from src.api.shared_schemas.product import Product, ProductOut
from src.api.shared_schemas.rating import RatingsSummaryOut
from src.api.shared_schemas.store import Store, StoreSchema
from src.api.shared_schemas.store_city import StoreCitySchema


from src.api.shared_schemas.store_hours import StoreHoursOut
from src.api.shared_schemas.store_operation_config import StoreOperationConfigOut

from src.api.shared_schemas.variant import Variant


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

    model_config = ConfigDict(
        from_attributes=True,
        arbitrary_types_allowed=True,
        populate_by_name=True
    )
