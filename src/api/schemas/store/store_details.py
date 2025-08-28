# ✅ CORRETO - Importação direta para runtime
from typing import Optional, List

from pydantic import Field
from src.api.schemas.category import CategoryOut
from src.api.schemas.payment_method import PaymentMethodGroupOut
from src.api.schemas.rating import RatingsSummaryOut

from src.api.schemas.product.product import ProductOut
from src.api.schemas.store.store import StoreSchema
from src.api.schemas.variant.variant import Variant
from src.api.schemas.coupon import CouponOut
from src.api.schemas.store.scheduled_pauses import ScheduledPauseOut

# ✅ Use os tipos diretamente (sem aspas):
class StoreDetails(StoreSchema):
    payment_method_groups: list[PaymentMethodGroupOut] = []
    ratingsSummary: Optional[RatingsSummaryOut] = Field(None, alias="ratingsSummary")
    categories: List[CategoryOut] = []

    products: List[ProductOut] = []
    variants: List[Variant] = []
    coupons: List[CouponOut] = []
    scheduled_pauses: list[ScheduledPauseOut] = []