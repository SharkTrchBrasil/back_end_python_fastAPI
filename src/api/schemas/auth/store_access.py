from pydantic import BaseModel

from src.api.schemas.auth.user import UserSchema
from src.api.schemas.store.store import RoleSchema


class StoreAccess(BaseModel):
    user: UserSchema
    role: RoleSchema