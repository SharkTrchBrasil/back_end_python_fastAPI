from enum import Enum
from pydantic import BaseModel, Field, computed_field
from typing import Optional

from src.api.shared_schemas.store_delivery_options import StoreDeliveryConfig
from src.core.aws import get_presigned_url


class Roles(Enum):
    OWNER = 'owner'
    ADMIN = 'admin'


class StoreBase(BaseModel):
    id: int
    name: str = Field(min_length=4, max_length=100)

    phone: str

    # Endereço
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
    delivery_config: Optional[StoreDeliveryConfig] = None  # Nested Delivery Config

    # Imagem é opcional
    file_key: Optional[str] = None

    #store_url: str

    @computed_field
    @property
    def image_path(self) -> str:
        return get_presigned_url(self.file_key) if self.file_key else ""



    model_config = {
        "from_attributes": True,
        "arbitrary_types_allowed": True # ADICIONE ESTA LINHA AQUI
    }

class Store(StoreBase):
    id: int


class StoreCreate(StoreBase):
    name: str = Field(min_length=4, max_length=100)
    phone: str = Field(min_length=10, max_length=15)


class Role(BaseModel):
    machine_name: str


class StoreWithRole(BaseModel):
    store: Store
    role: Role

class StoreUpdate(BaseModel):
    name: Optional[str]
    phone: Optional[str]
    zip_code: Optional[str]
    street: Optional[str]
    number: Optional[str]
    neighborhood: Optional[str]
    complement: Optional[str]
    reference: Optional[str]
    city: Optional[str]
    state: Optional[str]
    instagram: Optional[str]
    facebook: Optional[str]
    tiktok: Optional[str]
    plan_type: Optional[str]
    file_key: Optional[str]
    #store_url: Optional[str]

    @computed_field
    @property
    def image_path(self) -> str:
        return get_presigned_url(self.file_key)

