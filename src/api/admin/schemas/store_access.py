from pydantic import BaseModel

from src.api.admin.schemas.user import User
from src.api.shared_schemas.store import Role


class StoreAccess(BaseModel):
    user: User
    role: Role