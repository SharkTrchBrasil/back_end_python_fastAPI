# schemas/store/role.py
from pydantic import ConfigDict
from ..base_schema import AppBaseModel


class RoleSchema(AppBaseModel):
    machine_name: str
    model_config = ConfigDict(from_attributes=True)