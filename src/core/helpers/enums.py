from enum import Enum

class CashMovementType(str, Enum):
    IN = "in"
    OUT = "out"
class CashierTransactionType(str, Enum):
    SALE = "SALE"  # Alterado para maiúsculas
    REFUND = "REFUND"  # Alterado para maiúsculas
    INFLOW = "INFLOW"  # Alterado para maiúsculas
    OUTFLOW = "OUTFLOW"  # Alterado para maiúsculas
    WITHDRAW = "WITHDRAW"  # Alterado para maiúsculas
    SANGRIA = "SANGRIA"  # Alterado para maiúsculas

class PaymentMethod(str, Enum):
    CASH = "cash"
    CREDIT = "credit_card"
    DEBIT = "debit_card"
    PIX = "pix"
