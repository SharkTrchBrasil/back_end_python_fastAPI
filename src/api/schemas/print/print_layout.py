# src/api/schemas/print/print_layout.py (NOVO ARQUIVO)

from pydantic import BaseModel, Field, ConfigDict
from typing import List
from datetime import datetime

# --- Schema Base com todos os campos configuráveis ---
class PrintLayoutConfigBase(BaseModel):
    auto_print: bool = Field(default=False)
    copies: int = Field(default=1, ge=1, le=5)
    show_client_data: bool = Field(default=True)
    show_order_values: bool = Field(default=True)
    show_payment_method: bool = Field(default=True)
    highlight_order_number: bool = Field(default=False)
    highlight_priority: bool = Field(default=False)
    highlight_delivery_estimate: bool = Field(default=False)
    highlight_item_quantity: bool = Field(default=False)
    highlight_complements: bool = Field(default=False)
    highlight_observations: bool = Field(default=False)
    linked_printers: List[str] = Field(default_factory=list)

# --- Schema para criar/atualizar uma configuração ---
class PrintLayoutConfigUpdate(PrintLayoutConfigBase):
    pass

# --- Schema para retornar os dados para o frontend ---
class PrintLayoutConfigOut(PrintLayoutConfigBase):
    id: int
    store_id: int
    destination: str
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)