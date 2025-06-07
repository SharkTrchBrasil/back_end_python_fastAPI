from pydantic import BaseModel, ConfigDict


class StoreThemeIn(BaseModel):
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

class StoreThemeOut(StoreThemeIn):
    store_id: int

    model_config = ConfigDict(from_attributes=True, extra="forbid")