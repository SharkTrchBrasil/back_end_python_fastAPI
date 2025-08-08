from decimal import Decimal
from pydantic import BaseModel, computed_field, Field

# ✅ ADICIONADO: Importe o Enum que criamos
from src.core.models import CashbackType
from src.core.aws import get_presigned_url


# --- Schemas de Categoria Atualizados ---

class CategoryBase(BaseModel):
    """Campos base de uma categoria."""
    name: str
    priority: int
    is_active: bool


class CategoryCreate(CategoryBase):
    """Schema para criar uma nova categoria, com campos de cashback opcionais."""
    # O frontend enviará o tipo como string ('none', 'fixed', 'percentage')
    cashback_type: CashbackType = Field(default=CashbackType.NONE)
    # O valor pode ser o percentual (ex: 5 para 5%) ou o valor fixo em centavos
    cashback_value: Decimal = Field(default=Decimal('0.00'))


class CategoryUpdate(BaseModel):
    """Schema para atualizar uma categoria, todos os campos são opcionais."""
    name: str | None = None
    priority: int | None = None
    is_active: bool | None = None

    # ✅ ADICIONADO: Campos para atualizar a regra de cashback
    cashback_type: CashbackType | None = None
    cashback_value: Decimal | None = None


class CategoryOut(CategoryBase):
    """Schema de resposta da API, incluindo os dados de cashback."""
    id: int
    file_key: str = Field(exclude=True)

    # ✅ ADICIONADO: Retornando as regras de cashback salvas
    cashback_type: CashbackType
    cashback_value: Decimal

    model_config = {
        "from_attributes": True
    }

    @computed_field
    @property
    def image_path(self) -> str:
        """Gera a URL da imagem a partir da file_key."""
        return get_presigned_url(self.file_key) if self.file_key else None