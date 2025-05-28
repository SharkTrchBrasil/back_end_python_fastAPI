from enum import Enum

class CashMovementType(str, Enum):
    IN = "in"
    OUT = "out"




class CashierTransactionType(str, Enum):
    SALE = "sale"
    REFUND = "refund"
    INFLOW = "inflow"  # Mantenha em minúsculas
    OUTFLOW = "outflow" # Mantenha em minúsculas
    WITHDRAW = "withdraw" # Mantenha em minúsculas
    SANGRIA = "sangria" # Mantenha em minúsculas

class PaymentMethod(str, Enum):
    CASH = "cash"
    CREDIT = "credit_card"
    DEBIT = "debit_card"
    PIX = "pix"
