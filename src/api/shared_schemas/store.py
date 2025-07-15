from enum import Enum
from pydantic import BaseModel, Field, computed_field
from typing import Optional

from src.api.admin.schemas.subscription import StoreSubscriptionOut
from src.api.shared_schemas.store_delivery_options import StoreDeliveryConfig
from src.core.aws import get_presigned_url



class Roles(Enum):
    OWNER = 'owner'
    ADMIN = 'admin'


class StoreBase(BaseModel):
    name: str = Field(min_length=4, max_length=100)
    phone: str = Field(min_length=10, max_length=15)

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
    store_url: Optional[str] = None
    # Imagem (opcional)
    file_key: Optional[str] = None
    # No StoreBase
    banner_file_key: Optional[str] = None

    @computed_field
    @property
    def banner_path(self) -> str:
        return get_presigned_url(self.banner_file_key) if self.banner_file_key else ""


    @computed_field
    @property
    def image_path(self) -> str:
        return get_presigned_url(self.file_key) if self.file_key else ""

    model_config = {
        "from_attributes": True,
        "arbitrary_types_allowed": True
    }


# Usado na criação (POST)
class StoreCreate(StoreBase):
    pass


# Usado na resposta (GET etc)
class Store(StoreBase):
    id: int
    subscription: Optional[StoreSubscriptionOut]

# Role e Store com role (exibição do cargo do usuário)
class Role(BaseModel):
    machine_name: str


class StoreWithRole(BaseModel):
    store: Store
    role: Role


# Atualização (PATCH)
class StoreUpdate(BaseModel):
    name: Optional[str] = None
    phone: Optional[str] = None
    zip_code: Optional[str] = None
    street: Optional[str] = None
    number: Optional[str] = None
    neighborhood: Optional[str] = None
    complement: Optional[str] = None
    reference: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    instagram: Optional[str] = None
    facebook: Optional[str] = None
    tiktok: Optional[str] = None
    plan_type: Optional[str] = None


    file_key: Optional[str] = None
    banner_file_key: Optional[str] = None

    @computed_field
    @property
    def image_path(self) -> str:
        return get_presigned_url(self.file_key) if self.file_key else ""

    @computed_field
    @property
    def banner_path(self) -> str:
        return get_presigned_url(self.banner_file_key) if self.banner_file_key else ""
