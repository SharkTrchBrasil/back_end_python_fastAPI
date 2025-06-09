from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field, computed_field

from src.core.aws import get_presigned_url


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
        return get_presigned_url(self.file_key)

    class Config:
        from_attributes = True
