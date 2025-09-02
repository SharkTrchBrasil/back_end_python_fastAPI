from pydantic import BaseModel
from datetime import datetime
from decimal import Decimal

class WalletSummaryOut(BaseModel):
    """Schema para o resumo rápido da carteira."""
    # Usamos `int` para manter a consistência com os preços em centavos do seu sistema
    cashback_balance: int

    class Config:
        from_attributes = True

class CashbackTransactionOut(BaseModel):
    """Schema para um item no extrato de cashback."""
    id: int
    amount: Decimal # Usamos Decimal aqui para exibir o valor formatado (ex: R$ 2,50)
    type: str # 'generated', 'used', 'expired'
    description: str
    created_at: datetime

    class Config:
        from_attributes = True