from enum import Enum
from pydantic import BaseModel, computed_field, Field
from typing import Optional


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

    # Redes sociais
    instagram: Optional[str] = None
    facebook: Optional[str] = None

    # Plano
    plan_type: str = "free"

    file_key: str = Field(exclude=True)

    @computed_field
    @property
    def image_path(self) -> str:
        return get_presigned_url(self.file_key)

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


    file_key: Optional[str] = None

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
