# schemas/store/store_access.py
from ..base_schema import AppBaseModel
from .role import RoleSchema
from ..user import UserSchema


class StoreAccess(AppBaseModel):
    user: UserSchema
    role: RoleSchema