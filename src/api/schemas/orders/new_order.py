from pydantic import BaseModel
from typing import Optional

# Este é o novo payload que o Flutter vai enviar.
# Apenas as informações que o backend ainda não sabe.
class CreateOrderInput(BaseModel):
    payment_method_id: int
    delivery_type: str
    observation: Optional[str] = None
    needs_change: Optional[bool] = False
    change_for: Optional[float] = None # Em reais, ex: 50.00
    # O ID do endereço pode ser opcional se o usuário retirar na loja
    address_id: Optional[int] = None
    delivery_fee: Optional[int] = None