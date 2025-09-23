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



class OrderStatus(str, enum.Enum):
    """
    Representa o ciclo de vida completo de um pedido.
    """
    # Fase Inicial
    PENDING = 'pending'      # Pedido recém-criado, aguardando confirmação do restaurante.
    ACCEPTED = 'accepted'    # Restaurante confirmou que irá preparar o pedido.

    # Fase de Preparo
    PREPARING = 'preparing'  # Pedido está sendo preparado na cozinha.
    READY = 'ready'          # Pedido pronto para retirada ou para o entregador.

    # Fase de Entrega
    ON_ROUTE = 'on_route'    # Pedido saiu para entrega com o entregador.
    DELIVERED = 'delivered'  # Cliente recebeu o pedido.

    # Fase de Conclusão
    FINALIZED = 'finalized'  # Pedido concluído (pagamento verificado, ciclo encerrado).
    CANCELED = 'canceled'    # Pedido foi cancelado em alguma etapa.



class PayableStatus(str, enum.Enum):
    pending = "pending"
    paid = "paid"
    overdue = "overdue"
    cancelled = "cancelled"


class ThemeMode(enum.Enum):
    LIGHT = "light"
    DARK = "dark"


# Usamos um Enum para garantir que o tipo seja sempre um dos valores esperados
class CategoryType(str, enum.Enum):
    GENERAL = "GENERAL"
    CUSTOMIZABLE = "CUSTOMIZABLE"



# ✅ 1. CRIE UM ENUM PYTHON PARA AS TAGS
class FoodTagEnum(str, enum.Enum):
    VEGETARIAN = "Vegetariano"
    VEGAN = "Vegano"
    ORGANIC = "Orgânico"
    SUGAR_FREE = "Sem açúcar"
    LAC_FREE = "Zero lactose"



class BeverageTagEnum(str, enum.Enum):
    COLD_DRINK = "Bebida gelada"
    ALCOHOLIC = "Bebida alcoólica"
    NATURAL = "Natural"

class AvailabilityTypeEnum(str, enum.Enum):
    ALWAYS = "ALWAYS"
    SCHEDULED = "SCHEDULED"

class PricingStrategyType(str, enum.Enum):
    SUM_OF_ITEMS = "SUM_OF_ITEMS"
    HIGHEST_PRICE = "HIGHEST_PRICE"
    LOWEST_PRICE = "LOWEST_PRICE"




class CategoryTemplateType(str, enum.Enum):
    NONE = "NONE"  # For when no template is applicable (ex: General Category)
    PIZZA = "PIZZA"
    ACAI = "ACAI"
    SNACKS = "SNACKS"
    SUSHI = "SUSHI"
    SALADS = "SALADS"
    DESSERTS = "DESSERTS"
    DRINKS = "DRINKS"
    BREAKFAST = "BREAKFAST"
    LUNCH_BOXES = "LUNCH_BOXES"
    BLANK = "BLANK"  # For the "Start from Scratch" option


class OptionGroupType(str, enum.Enum):
    """Define o comportamento especial de um grupo de opções."""

    # Um grupo especial para Tamanhos, usado em categorias onde o preço varia por tamanho.
    # A UI pode usar este tipo para mostrar campos específicos (ex: fatias, sabores máx).
    SIZE = "SIZE"

    # Um grupo genérico de opções, onde cada item pode ter um preço aditivo.
    # Usado para a maioria dos casos (ex: Massas, Bordas, Frutas, Caldas).
    GENERIC = "GENERIC"




class ProductStatus(str, enum.Enum):
    ACTIVE = "ACTIVE"       # Visível e à venda
    INACTIVE = "INACTIVE"   # Pausado temporariamente, mas ainda no catálogo principal
    ARCHIVED = "ARCHIVED"   # "Deletado", oculto de todas as listas principais



# Enum para agrupar os tipos de mensagem, como na UI
class ChatbotMessageGroupEnum(enum.Enum):
    SALES_RECOVERY = "Recuperador de Vendas"
    CUSTOMER_QUESTIONS = "Resolva as perguntas dos seus clientes"
    GET_REVIEWS = "Obtenha avaliações dos seus clientes"
    LOYALTY = "Ative seu programa de fidelidade"
    ORDER_UPDATES = "Envie atualizações automáticas do pedido"
    COURIER_NOTIFICATIONS = "Notifique seus Entregadores"