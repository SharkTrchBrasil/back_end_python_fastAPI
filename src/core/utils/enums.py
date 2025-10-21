# NOVO: Criamos um Enum para os tipos de cashback
import enum


class Roles(enum.Enum):
    """
    Funções/Roles disponíveis no sistema.
    IMPORTANTE: Mantenha sincronizado com db_initialization.py e o frontend.
    """
    OWNER = 'owner'          # Proprietário (acesso total, não pode ser criado via API)
    MANAGER = 'manager'      # Gerente (pode gerenciar tudo exceto outros proprietários)
    CASHIER = 'cashier'      # Caixa (foco em vendas e pagamentos)
    WAITER = 'waiter'        # Garçom (foco em pedidos de mesas)
    STOCK_MANAGER = 'stock_manager'  # ✅ Gerente de Estoque (controle de produtos)


class CashbackType(enum.Enum):
    NONE = "none"
    FIXED = "fixed"
    PERCENTAGE = "percentage"


class TableStatus(str, enum.Enum): # Herdar de 'str' é uma boa prática
    AVAILABLE = "AVAILABLE"
    OCCUPIED = "OCCUPIED"
    RESERVED = "RESERVED"
    MAINTENANCE = "MAINTENANCE"
    CLEANING = "CLEANING"

# Faça o mesmo para CommandStatus para padronizar
class CommandStatus(str, enum.Enum):
    ACTIVE = "ACTIVE"
    CLOSED = "CLOSED"
    CANCELED = "CANCELED"

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

class ProductType(str, enum.Enum):
    # ✅ CORRIGIDO: Agora reflete exatamente o que está no banco de dados
    PREPARED = "PREPARED"
    IMPORTED = "IMPORTED"

class OrderStatus(str, enum.Enum):
    """
    Representa o ciclo de vida completo de um pedido.
    """
    # Fase Inicial
    PENDING = 'pending'      # Pedido recém-criado, aguardando confirmação do restaurante.
   # ACCEPTED = 'accepted'    # Restaurante confirmou que irá preparar o pedido.

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


# src/core/utils/enums.py

import enum


class AuditAction(str, enum.Enum):
    """Ações de auditoria do sistema"""

    # === PRODUTOS ===
    CREATE_PRODUCT = "create_product"
    UPDATE_PRODUCT = "update_product"
    DELETE_PRODUCT = "delete_product"
    ARCHIVE_PRODUCT = "archive_product"
    BULK_ARCHIVE_PRODUCTS = "bulk_archive_products"
    BULK_UPDATE_CATEGORY = "bulk_update_category"
    BULK_UPDATE_STATUS = "bulk_update_status"
    UPDATE_PRODUCT_PRICE = "update_product_price"
    ADD_PRODUCT_TO_CATEGORY = "add_product_to_category"
    REMOVE_PRODUCT_FROM_CATEGORY = "remove_product_from_category"

    # === CATEGORIAS ===
    CREATE_CATEGORY = "create_category"
    UPDATE_CATEGORY = "update_category"
    DELETE_CATEGORY = "delete_category"
    REORDER_CATEGORIES = "reorder_categories"

    # === VARIANTES/COMPLEMENTOS ===
    CREATE_VARIANT = "create_variant"
    UPDATE_VARIANT = "update_variant"
    DELETE_VARIANT = "delete_variant"
    LINK_VARIANT_TO_PRODUCT = "link_variant_to_product"
    UNLINK_VARIANT_FROM_PRODUCT = "unlink_variant_from_product"

    # === PEDIDOS ===
    CREATE_ORDER = "create_order"
    UPDATE_ORDER_STATUS = "update_order_status"
    CANCEL_ORDER = "cancel_order"
    APPLY_DISCOUNT = "apply_discount"

    # === CUPONS ===
    CREATE_COUPON = "create_coupon"
    UPDATE_COUPON = "update_coupon"
    DELETE_COUPON = "delete_coupon"
    ACTIVATE_COUPON = "activate_coupon"
    DEACTIVATE_COUPON = "deactivate_coupon"

    # === ACESSOS E PERMISSÕES ===
    GRANT_STORE_ACCESS = "grant_store_access"
    REVOKE_STORE_ACCESS = "revoke_store_access"
    UPDATE_USER_ROLE = "update_user_role"

    # === LOJAS ===
    CREATE_STORE = "create_store"
    UPDATE_STORE_SETTINGS = "update_store_settings"
    UPDATE_OPERATION_CONFIG = "update_operation_config"
    UPDATE_THEME = "update_theme"
    UPDATE_PAYMENT_METHODS = "update_payment_methods"

    # === ASSINATURAS (BILLING) ✅ NOVAS ===
    CREATE_SUBSCRIPTION = "create_subscription"
    REACTIVATE_SUBSCRIPTION = "reactivate_subscription"
    UPDATE_SUBSCRIPTION_CARD = "update_subscription_card"
    CANCEL_SUBSCRIPTION = "cancel_subscription"
    SUBSCRIPTION_PAYMENT_SUCCESS = "subscription_payment_success"
    SUBSCRIPTION_PAYMENT_FAILED = "subscription_payment_failed"

    # === FINANCEIRO - CAIXA ✅ NOVAS ===
    OPEN_CASHIER = "open_cashier"
    CLOSE_CASHIER = "close_cashier"
    ADD_CASH = "add_cash"
    REMOVE_CASH = "remove_cash"
    CASHIER_ADJUSTMENT = "cashier_adjustment"
    CASHIER_DISCREPANCY = "cashier_discrepancy"

    # === FINANCEIRO - CONTAS ===
    CREATE_PAYABLE = "create_payable"
    UPDATE_PAYABLE = "update_payable"
    DELETE_PAYABLE = "delete_payable"
    PAY_PAYABLE = "pay_payable"

    # === FORMAS DE PAGAMENTO ✅ NOVAS ===
    ACTIVATE_PAYMENT_METHOD = "activate_payment_method"
    DEACTIVATE_PAYMENT_METHOD = "deactivate_payment_method"
    UPDATE_PAYMENT_METHOD_FEE = "update_payment_method_fee"
    UPDATE_PAYMENT_METHOD_CONFIG = "update_payment_method_config"

    # === MESAS E COMANDAS ===
    CREATE_TABLE = "create_table"
    UPDATE_TABLE_STATUS = "update_table_status"
    DELETE_TABLE = "delete_table"
    CREATE_COMMAND = "create_command"
    CLOSE_COMMAND = "close_command"

    # === CLIENTES ===
    CREATE_CUSTOMER = "create_customer"
    UPDATE_CUSTOMER = "update_customer"
    DELETE_CUSTOMER = "delete_customer"

    # === SISTEMA ===
    LOGIN = "login"
    LOGOUT = "logout"
    FAILED_LOGIN = "failed_login"
    PASSWORD_CHANGE = "password_change"
    DATA_EXPORT = "data_export"
    DATA_IMPORT = "data_import"


class AuditEntityType(str, enum.Enum):
    """Tipos de entidades que podem ser auditadas"""
    PRODUCT = "product"
    CATEGORY = "category"
    VARIANT = "variant"
    ORDER = "order"
    CUSTOMER = "customer"
    COUPON = "coupon"
    STORE_ACCESS = "store_access"
    USER = "user"
    STORE = "store"
    STORE_SETTINGS = "store_settings"

    # ✅ NOVAS ENTIDADES
    SUBSCRIPTION = "subscription"
    PAYMENT_METHOD = "payment_method"
    CASHIER_SESSION = "cashier_session"
    CASHIER_TRANSACTION = "cashier_transaction"

    PAYABLE = "payable"
    TABLE = "table"
    COMMAND = "command"
    CART = "cart"