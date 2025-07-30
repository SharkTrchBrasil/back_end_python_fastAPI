import enum
from pydantic import BaseModel, ConfigDict

class AppBaseModel(BaseModel):
    # Configuração padrão para todos os nossos schemas
    model_config = ConfigDict(
        from_attributes=True,  # Permite criar schemas a partir de objetos ORM
        extra="forbid"
    )

class VariantType(str, enum.Enum):
    INGREDIENTS = "Ingredientes"
    SPECIFICATIONS = "Especificações"
    CROSS_SELL = "Cross-sell"
    DISPOSABLES = "Descartáveis" # ✅ ESTA OPÇÃO ESTAVA FALTANDO

class UIDisplayMode(str, enum.Enum):
    SINGLE = "Seleção Única"
    MULTIPLE = "Seleção Múltipla"
    QUANTITY = "Seleção com Quantidade"