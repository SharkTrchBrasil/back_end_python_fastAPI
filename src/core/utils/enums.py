# NOVO: Criamos um Enum para os tipos de cashback
import enum


class Roles(enum.Enum):
    OWNER = 'owner'
    MANAGER = 'manager'
    ADMIN = 'admin'


class CashbackType(enum.Enum):
    NONE = "none"
    FIXED = "fixed"
    PERCENTAGE = "percentage"


class TableStatus(enum.Enum):
    AVAILABLE = "available"
    OCCUPIED = "occupied"
    RESERVED = "reserved"
    MAINTENANCE = "maintenance"
    CLEANING = "cleaning"


class CommandStatus(enum.Enum):
    ACTIVE = "active"
    CLOSED = "closed"
    CANCELED = "canceled"

# Enum para o status de verificação
class StoreVerificationStatus(enum.Enum):
    UNVERIFIED = "unverified"
    PENDING = "pending"
    VERIFIED = "verified"
    REJECTED = "rejected"


# Defina seu Enum para os tipos
class PaymentMethodType(enum.Enum):
    CASH = "CASH"
    OFFLINE_CARD = "OFFLINE_CARD"
    MANUAL_PIX = "MANUAL_PIX"
    ONLINE_GATEWAY = "ONLINE_GATEWAY"


class CashierTransactionType(str, enum.Enum):
    SALE = "sale"
    REFUND = "refund"
    INFLOW = "inflow"  # Mantenha em minúsculas
    OUTFLOW = "outflow" # Mantenha em minúsculas
    WITHDRAW = "withdraw" # Mantenha em minúsculas
    SANGRIA = "sangria" # Mantenha em minúsculas

class PaymentMethod(str, enum.Enum):
    CASH = "cash"
    CREDIT = "credit_card"
    DEBIT = "debit_card"
    PIX = "pix"


class CartStatus(str, enum.Enum):
    ACTIVE = "active"
    COMPLETED = "completed"
    ABANDONED = "abandoned"

class ProductType(enum.Enum):
    INDIVIDUAL = "INDIVIDUAL"
    KIT = "KIT"