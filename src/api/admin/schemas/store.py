from enum import Enum
from pydantic import BaseModel, Field

from src.api.admin.schemas.user import User

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


class Store(StoreBase):
    id: int



class StoreCreate(StoreBase):
     pass



class StoreUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=4, max_length=20)
    language: str | None = Field(default=None, min_length=2, max_length=2)
    country: str | None = Field(default=None, min_length=2, max_length=2)
    currency: str | None = Field(default=None, min_length=3, max_length=3)
    phone: str
    is_active: bool



class Role(BaseModel):
    machine_name: str


class StoreWithRole(BaseModel):
    store: Store
    role: Role
