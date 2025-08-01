from pydantic import BaseModel

from src.api.admin.schemas.user import UserSchema
from src.api.shared_schemas.store import RoleSchema


class StoreAccess(BaseModel):
    user: UserSchema
    role: RoleSchema