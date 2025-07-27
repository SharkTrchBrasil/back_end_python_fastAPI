from typing import Optional, List
from pydantic import Field, ConfigDict

# Importe seus schemas existentes
from src.api.admin.schemas.store_settings import StoreSettingsBase
from src.api.admin.schemas.store_subscription import StoreSubscriptionSchema
from src.api.shared_schemas.category import Category
from src.api.shared_schemas.coupon import CouponOut
from src.api.shared_schemas.payment_method import StorePaymentMethods
from src.api.shared_schemas.product import Product, ProductOut
from src.api.shared_schemas.rating import RatingsSummaryOut
from src.api.shared_schemas.store import Store
from src.api.shared_schemas.store_city import StoreCitySchema
from src.api.shared_schemas.store_delivery_options import StoreDeliveryConfigBase
from src.api.shared_schemas.store_hours import StoreHoursSchema
from src.api.shared_schemas.variant import Variant


class StoreDetails(Store):
    # --- Relações que você já tinha ---
    payment_methods: list[StorePaymentMethods] = []
    delivery_config: StoreDeliveryConfigBase | None = None
    hours: list[StoreHoursSchema] = []
    cities: list[StoreCitySchema] = []
    store_settings: StoreSettingsBase | None = None
    ratingsSummary: Optional[RatingsSummaryOut] = Field(None, alias="ratingsSummary")
    subscription: Optional[StoreSubscriptionSchema] = None

    # --- NOVAS RELAÇÕES DO CATÁLOGO ---
    # Adicionamos os campos que agora são carregados pela "super consulta".
    categories: List[Category] = []
    products: List[ProductOut] = []
    variants: List[Variant] = []
    coupons: List[CouponOut] = []

    model_config = ConfigDict(
        from_attributes=True,
        arbitrary_types_allowed=True,
        populate_by_name=True
    )
