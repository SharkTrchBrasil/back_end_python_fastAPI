from typing import Optional

from pydantic import Field

from src.api.shared_schemas.payment_method import StorePaymentMethods
from src.api.shared_schemas.rating import RatingsSummaryOut
from src.api.shared_schemas.store import Store
from src.api.shared_schemas.store_city import StoreCityBaseSchema

from src.api.shared_schemas.store_delivery_options import StoreDeliveryConfigBase
from src.api.shared_schemas.store_hours import StoreHoursSchema




class StoreDetails(Store):
    payment_methods: list[StorePaymentMethods] = []
    delivery_config: StoreDeliveryConfigBase | None = None
    hours: list[StoreHoursSchema] = []
    cities: list[StoreCityBaseSchema] = []

    ratingsSummary: Optional[RatingsSummaryOut] = Field(None, alias="ratingsSummary")



    model_config = {
        "from_attributes": True,
        "arbitrary_types_allowed": True
    }

