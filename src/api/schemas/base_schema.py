import enum
from pydantic import BaseModel, ConfigDict

class AppBaseModel(BaseModel):
    # Configuração padrão para todos os nossos schemas
    model_config = ConfigDict(
        from_attributes=True,  # Permite criar schemas a partir de objetos ORM
        extra="forbid"
    )

