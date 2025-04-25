from pydantic import BaseModel, computed_field, Field

from src.core.aws import get_presigned_url


class Category(BaseModel):
    id: int
    name: str
    priority: int
    file_key: str = Field(exclude=True)

    @computed_field
    @property
    def image_path(self) -> str:
        return get_presigned_url(self.file_key)