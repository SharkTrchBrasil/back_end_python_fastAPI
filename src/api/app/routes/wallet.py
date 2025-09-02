from fastapi import APIRouter
from typing import List

from src.core import models
from src.core.database import GetDBDep
from src.core.dependencies import GetCurrentUserDep  # Dependência para pegar o usuário logado
from src.api.schemas.customer.wallet import WalletSummaryOut, CashbackTransactionOut

# O prefixo '/wallet' é limpo e semântico
router = APIRouter(tags=["Wallet"], prefix="/wallet")


@router.get("/summary", response_model=WalletSummaryOut)
def get_wallet_summary(current_user: GetCurrentUserDep):
    """
    Retorna o saldo de cashback atual do cliente logado.
    """
    # A dependência `GetCurrentUserDep` já nos dá o objeto do usuário.
    # Acessar o saldo é direto e muito rápido.
    return {"cashback_balance": current_user.cashback_balance}


@router.get("/transactions", response_model=List[CashbackTransactionOut])
def get_wallet_transactions(current_user: GetCurrentUserDep, db: GetDBDep):
    """
    Retorna o histórico de transações de cashback (extrato) do cliente logado.
    """
    transactions = db.query(models.CashbackTransaction).filter(
        models.CashbackTransaction.user_id == current_user.id
    ).order_by(
        models.CashbackTransaction.created_at.desc()  # Ordena da mais recente para a mais antiga
    ).all()

    return transactions