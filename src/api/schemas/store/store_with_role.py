# Em: src/api/schemas/store/store_with_role.py (NOVO ARQUIVO)

from pydantic import BaseModel, ConfigDict
from src.api.schemas.store.store_details import StoreDetails


class RoleSchema(BaseModel):
    machine_name: str
    model_config = ConfigDict(from_attributes=True)


class StoreWithRole(BaseModel):
    """
    Schema unificado que sempre retorna StoreDetails (com subscription calculada).
    """
    store: StoreDetails
    role: RoleSchema

    model_config = ConfigDict(from_attributes=True)