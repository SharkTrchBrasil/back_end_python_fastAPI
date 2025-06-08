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

    # Novas cores personalizadas
    sidebar_background_color: str
    sidebar_text_color: str
    sidebar_icon_color: str
    category_background_color: str
    category_text_color: str
    product_background_color: str
    product_text_color: str
    price_text_color: str
    cart_background_color: str
    cart_text_color: str

    # Novos campos para layout e tema
    category_layout: str
    product_layout: str
    theme_name: str

class StoreThemeOut(StoreThemeIn):
    store_id: int

    model_config = ConfigDict(from_attributes=True, extra="forbid")