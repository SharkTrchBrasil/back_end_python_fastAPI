from enum import Enum

class CashMovementType(str, Enum):
    IN = "in"
    OUT = "out"

class CashierTransactionType(str, Enum):
    SALE = "sale"
    REFUND = "refund"
    INFLOW = "inflow"
    OUTFLOW = "outflow"
    WITHDRAW = "withdraw"
    SANGRIA = "sangria"

class PaymentMethod(str, Enum):
    CASH = "cash"
    CREDIT = "credit_card"
    DEBIT = "debit_card"
    PIX = "pix"
