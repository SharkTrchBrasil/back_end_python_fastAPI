# schemas/store/tokenized_card.py
from ..base_schema import AppBaseModel


class TokenizedCard(AppBaseModel):
    payment_token: str
    card_mask: str