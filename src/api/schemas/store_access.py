from pydantic import BaseModel

from src.api.schemas.user import UserSchema
from src.api.schemas.store import RoleSchema


class StoreAccess(BaseModel):
    user: UserSchema
    role: RoleSchema