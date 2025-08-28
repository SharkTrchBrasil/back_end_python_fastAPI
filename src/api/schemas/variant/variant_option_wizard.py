# schemas/variant/variant_option_wizard.py
from typing import Optional

from ..base_schema import AppBaseModel


class VariantOptionCreateInWizard(AppBaseModel):
    name_override: str
    price_override: int = 0
    pos_code: Optional[str] = None
    available: bool = True