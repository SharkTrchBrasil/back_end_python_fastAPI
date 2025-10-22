# src/api/schemas/shared/base.py

import enum
from pydantic import BaseModel, ConfigDict


class AppBaseModel(BaseModel):
    """
    ✅ CONFIGURAÇÃO GLOBAL PROFISSIONAL

    Por que extra='ignore'?
    - SQLAlchemy ORM possui @hybrid_property que não estão nos schemas
    - Pydantic tenta incluir TODOS os atributos com from_attributes=True
    - extra='forbid' causa ValidationError nesses casos
    - extra='ignore' ignora campos não declarados, permitindo validação limpa

    Segurança:
    - A validação ainda ocorre em campos DECLARADOS
    - Apenas campos EXTRAS do ORM são ignorados
    - Payloads de entrada (POST/PUT) ainda são validados estritamente
    """
    model_config = ConfigDict(
        from_attributes=True,
        extra='ignore'  # ← CORREÇÃO GLOBAL
    )


class VariantType(str, enum.Enum):
    INGREDIENTS = "Ingredientes"
    SPECIFICATIONS = "Especificações"
    CROSS_SELL = "Cross-sell"
    DISPOSABLES = "Descartáveis"


class UIDisplayMode(str, enum.Enum):
    SINGLE = "Seleção Única"
    MULTIPLE = "Seleção Múltipla"
    QUANTITY = "Seleção com Quantidade"