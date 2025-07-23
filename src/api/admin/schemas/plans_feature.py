# schemas/feature_schema.py

from pydantic import BaseModel
from pydantic import ConfigDict

class FeatureSchema(BaseModel):
    """Schema para serializar os dados de uma funcionalidade."""
    model_config = ConfigDict(from_attributes=True)

    id: int
    feature_key: str
    name: str
    description: str | None
    is_addon: bool
    addon_price: int | None