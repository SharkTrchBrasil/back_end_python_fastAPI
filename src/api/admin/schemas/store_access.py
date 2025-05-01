from pydantic import BaseModel

from src.api.admin.schemas.store import Role
from src.api.admin.schemas.user import User


class StoreAccess(BaseModel):
    user: User
    role: Role