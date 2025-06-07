from typing import Optional
from pydantic import BaseModel, Field, computed_field

from src.core.aws import get_presigned_url


class BannerBase(BaseModel):
    store_id: int
    product_id: Optional[int] = None
    category_id: Optional[int] = None
    is_active: bool = True
    position: Optional[int] = None


class BannerIn(BannerBase):
    file_key: str


class BannerOut(BannerBase):
    id: int

    file_key: str = Field(exclude=True)

    @computed_field
    @property
    def image_path(self) -> str:
        return get_presigned_url(self.file_key)

    class Config:
        from_attributes = True
