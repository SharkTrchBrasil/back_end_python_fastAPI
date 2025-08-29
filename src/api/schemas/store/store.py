from __future__ import annotations
from pydantic import Field, computed_field, ConfigDict
from typing import List, Optional, TYPE_CHECKING

from src.core.utils.enums import StoreVerificationStatus
from src.core.aws import get_presigned_url

from ..base_schema import AppBaseModel
from .store_subscription import StoreSubscriptionSchema

class StoreBase(AppBaseModel):
    name: str = Field(min_length=3, max_length=100)
    url_slug: str
    description: Optional[str] = None
    phone: Optional[str] = Field(None, min_length=10, max_length=15)
    cnpj: Optional[str] = None
    segment_id: Optional[int] = None
    zip_code: Optional[str] = None
    street: Optional[str] = None
    number: Optional[str] = None
    complement: Optional[str] = None
    neighborhood: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    responsible_name: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    delivery_radius_km: Optional[float] = None
    average_preparation_time: Optional[int] = None
    tags: Optional[List[str]] = None
    meta_title: Optional[str] = None
    meta_description: Optional[str] = None
    file_key: Optional[str] = None
    banner_file_key: Optional[str] = None

class StoreCreate(AppBaseModel):
    name: str
    store_url: str
    description: Optional[str] = None
    phone: str
    cnpj: Optional[str] = None
    segment_id: int
    plan_id: int
    address: 'AddressCreate'
    responsible: 'ResponsibleCreate'

class StoreUpdate(StoreBase):
    name: Optional[str] = Field(None, min_length=3, max_length=100)
    url_slug: Optional[str] = None
    phone: Optional[str] = Field(None, min_length=10, max_length=15)
    is_setup_complete: Optional[bool] = None

class StoreSchema(StoreBase):
    id: int
    is_active: bool
    is_setup_complete: bool
    is_featured: bool
    verification_status: StoreVerificationStatus
    rating_average: float = 0.0
    rating_count: int = 0
    active_subscription: Optional[StoreSubscriptionSchema] = None

    @computed_field
    @property
    def image_path(self) -> str:
        return get_presigned_url(self.file_key) if self.file_key else ""

    @computed_field
    @property
    def banner_path(self) -> str:
        return get_presigned_url(self.banner_file_key) if self.banner_file_key else ""

    model_config = ConfigDict(from_attributes=True, arbitrary_types_allowed=True)

if TYPE_CHECKING:
    from .role import RoleSchema
    from .address import AddressCreate
    from .responsible import ResponsibleCreate

class StoreWithRole(AppBaseModel):
    store: StoreSchema
    role: 'RoleSchema'