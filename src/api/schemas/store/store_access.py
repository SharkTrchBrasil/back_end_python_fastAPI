from __future__ import annotations
from typing import TYPE_CHECKING
from ..base_schema import AppBaseModel
from .role import RoleSchema

if TYPE_CHECKING:
    from ..user import UserSchema

class StoreAccess(AppBaseModel):
    user: 'UserSchema'
    role: RoleSchema