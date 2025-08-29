# ARQUIVO: src/api/schemas/shared.py
from pydantic import computed_field

from src.api.schemas.base_schema import AppBaseModel
from src.core.aws import get_presigned_url

class ProductMinimal(AppBaseModel):
    id: int
    name: str
    base_price: int
    file_key: str | None = None

    @computed_field
    @property
    def image_path(self) -> str | None:
        """Gera a URL da imagem a partir da file_key."""
        return get_presigned_url(self.file_key) if self.file_key else None