from __future__ import annotations

from pydantic import computed_field

from src.api.schemas.base_schema import AppBaseModel
from src.core.aws import get_presigned_url, S3_PUBLIC_BASE_URL


class ProductMinimal(AppBaseModel):
    id: int
    name: str
    base_price: int
    file_key: str | None = None

    @computed_field
    @property
    def image_path(self) -> str | None:
        """Gera a URL da imagem a partir da file_key."""
        # ✅ 2. USE A NOVA LÓGICA DE URL ESTÁTICA E PERMANENTE
        return f"{S3_PUBLIC_BASE_URL}/{self.file_key}" if self.file_key else None