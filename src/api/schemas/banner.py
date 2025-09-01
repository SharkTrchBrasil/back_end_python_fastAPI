from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field, computed_field

from src.core.aws import get_presigned_url, S3_PUBLIC_BASE_URL


class BannerBase(BaseModel):
    product_id: Optional[int] = None
    category_id: Optional[int] = None
    is_active: Optional[bool] = True
    position: Optional[int] = None
    link_url: Optional[str] = None
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None


class BannerIn(BannerBase):
    file_key: str


class BannerOut(BannerBase):
    id: int

    # Isso será excluído da resposta
    file_key: str = Field(exclude=True)

    @computed_field
    @property
    def image_path(self) -> str:
        # ✅ 2. USE A NOVA LÓGICA DE URL ESTÁTICA E PERMANENTE
        return f"{S3_PUBLIC_BASE_URL}/{self.file_key}" if self.file_key else None

    class Config:
        from_attributes = True
