from pydantic import BaseModel


class TotemAuth(BaseModel):
    totem_token: str
    totem_name: str


class TotemCheckTokenResponse(BaseModel):
    granted: bool
    public_key: str
    store_id: int | None