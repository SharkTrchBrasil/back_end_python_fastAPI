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
