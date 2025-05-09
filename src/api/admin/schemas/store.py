from enum import Enum
from pydantic import BaseModel, Field
from typing import Optional

from pydantic_core.core_schema import computed_field

from src.api.admin.schemas.user import User
from src.core.aws import get_presigned_url


class Roles(Enum):
    OWNER = 'owner'
    ADMIN = 'admin'


class StoreBase(BaseModel):
    name: str = Field(min_length=4, max_length=20)
    language: str
    country: str
    currency: str
    phone: str
    is_active: bool

    # Endereço
    zip_code: str
    street: str
    number: str
    neighborhood: str
    complement: Optional[str] = None
    reference: Optional[str] = None
    city: str
    state: str

    # Identidade visual
    logo_url: Optional[str] = None
    logo_file_key: Optional[str] = Field(exclude=True)  # Renomeado para logo_file_key

    # Redes sociais
    instagram: Optional[str] = None
    facebook: Optional[str] = None

    # Plano
    plan_type: str = "free"

    @computed_field
    @property
    def logo_image_path(self) -> Optional[str]:  # Renomeado para logo_image_path
        if self.logo_file_key:
            return get_presigned_url(self.logo_file_key)
        return None

class Store(StoreBase):
    id: int


class StoreCreate(StoreBase):
    pass


class StoreUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=4, max_length=20)
    language: Optional[str] = Field(default=None, min_length=2, max_length=2)
    country: Optional[str] = Field(default=None, min_length=2, max_length=2)
    currency: Optional[str] = Field(default=None, min_length=3, max_length=3)
    phone: Optional[str] = None
    is_active: Optional[bool] = None

    # Endereço
    zip_code: Optional[str] = None
    street: Optional[str] = None
    number: Optional[str] = None
    neighborhood: Optional[str] = None
    complement: Optional[str] = None
    reference: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None

    # Identidade visual
    logo_url: Optional[str] = None

    # Redes sociais
    instagram: Optional[str] = None
    facebook: Optional[str] = None

    # Plano
    plan_type: Optional[str] = None


class Role(BaseModel):
    machine_name: str


class StoreWithRole(BaseModel):
    store: Store
    role: Role
