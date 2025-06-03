from typing import Optional

from pydantic import BaseModel, computed_field

from src.core.aws import get_presigned_url


class Store(BaseModel):
    id: int
    name: Optional[str]
    phone: Optional[str]
    zip_code: Optional[str]
    street: Optional[str]
    number: Optional[str]
    neighborhood: Optional[str]
    complement: Optional[str]
    reference: Optional[str]
    city: Optional[str]
    state: Optional[str]
    instagram: Optional[str]
    facebook: Optional[str]
    tiktok: Optional[str]
    plan_type: Optional[str]
    file_key: Optional[str]
    #store_url: Optional[str]

    @computed_field
    @property
    def image_path(self) -> str:
        return get_presigned_url(self.file_key)
    model_config = {
        "from_attributes": True
    }

class StoreTheme(BaseModel):
    primary_color: str
    secondary_color: str
    background_color: str
    card_color: str
    on_primary_color: str
    on_secondary_color: str
    on_background_color: str
    on_card_color: str
    inactive_color: str
    on_inactive_color: str
    font_family: str

    model_config = {
        "from_attributes": True
    }