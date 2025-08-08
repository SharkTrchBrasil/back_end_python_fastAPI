# Em: src/api/admin/schemas/order_schema.py (ou similar)

from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime


class PartialPaymentCreateSchema(BaseModel):
    # ✅ Aponta para o ID da ativação do método de pagamento, que é a fonte da verdade.
    # Não é opcional, pois todo pagamento precisa de um método.
    store_payment_method_activation_id: int

    amount: int  # Em centavos

    # ✅ Mantendo seus campos úteis!
    received_by: Optional[str] = None
    transaction_id: Optional[str] = None
    notes: Optional[str] = None



class PartialPaymentResponseSchema(BaseModel):
    id: int
    amount: int

    # ✅ Retorna o nome do método, muito mais útil para a UI do que um simples ID.
    payment_method_name: str

    received_by: Optional[str] = None
    transaction_id: Optional[str] = None
    notes: Optional[str] = None
    created_at: datetime  # É bom devolver o timestamp de quando foi criado.

    class Config:
        from_attributes = True  # Para Pydantic v2 (recomendado)
        # ou orm_mode = True para Pydantic v1