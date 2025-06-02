from pydantic import BaseModel, computed_field, Field, ConfigDict

from src.core.aws import get_presigned_url


class Category(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    priority: int
    file_key: str = Field(exclude=True)

    @computed_field
    @property
    def image_path(self) -> str:
        return get_presigned_url(self.file_key)