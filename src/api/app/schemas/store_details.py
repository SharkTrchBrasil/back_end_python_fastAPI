from typing import Optional

from pydantic import BaseModel, computed_field

from src.api.shared_schemas.payment_method import StorePaymentMethods
from src.api.shared_schemas.store_city import StoreCityBaseSchema
from src.api.shared_schemas.store_hours import StoreHoursSchema
from src.core.aws import get_presigned_url
from src.core.models import StoreDeliveryConfiguration


class StoreDetails(BaseModel):
    id: int
    name: str

    zip_code: Optional[str] = None
    street: Optional[str] = None
    number: Optional[str] = None
    neighborhood: Optional[str] = None
    complement: Optional[str] = None
    reference: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    description: Optional[str] = None

    # Redes sociais
    instagram: Optional[str] = None
    facebook: Optional[str] = None
    tiktok: Optional[str] = None

    # Plano
    plan_type: Optional[str] = "free"

    # Imagem é opcional
    file_key: Optional[str] = None


    @computed_field
    @property
    def image_path(self) -> str:
        return get_presigned_url(self.file_key) if self.file_key else ""

    payment_methods: list[StorePaymentMethods] = []
    delivery_config: StoreDeliveryConfiguration | None = None
    hours: list[StoreHoursSchema] = []
    cities: list[StoreCityBaseSchema] = []

    class Config:
        orm_mode = True
