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


class PaymentStatus(str, enum.Enum):
    """
    Status de pagamento do pedido.
    Indica o estado atual da transação financeira.
    """
    PENDING = 'pending'        # Aguardando pagamento
    PAID = 'paid'              # Pagamento confirmado
    PROCESSING = 'processing'  # Processando pagamento (para gateways online)
    FAILED = 'failed'          # Falha no pagamento
    REFUNDED = 'refunded'      # Pagamento reembolsado
    CANCELLED = 'cancelled'    # Pagamento cancelado

class SalesChannel(str, enum.Enum):
    """
    Canal de origem/venda do pedido.
    Define por onde o pedido foi realizado.
    """
    MENU = 'menu'  # Pedido feito pelo cardápio digital (QR Code)
    TABLE = 'table'                        # Pedido feito em mesa (garçom/comanda)
    COUNTER = 'counter'                    # Pedido feito no balcão
    PHONE = 'phone'                        # Pedido feito por telefone
    WHATSAPP = 'whatsapp'                  # Pedido feito pelo WhatsApp
    IFOOD = 'ifood'                        # Pedido do iFood (integração futura)
    RAPPI = 'rappi'                        # Pedido do Rappi (integração futura)
    UBER_EATS = 'uber_eats'                # Pedido do Uber Eats (integração futura)
    ADMIN_PANEL = 'admin_panel'            # Pedido criado pelo painel admin


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
    GLUTEN_FREE = "Sem glúten"
    SPICY = "Picante"
    KIDS = "Infantil"
    FITNESS = "Fitness"
    LOW_CARB = "Low Carb"


# Kitchen Status
class KitchenStatus(str, enum.Enum):
    NEW = "NEW"
    PREPARING = "PREPARING"
    READY = "READY"
    DELIVERED = "DELIVERED"
    CANCELLED = "CANCELLED"


# Waiter Call Status
class WaiterCallStatus(str, enum.Enum):
    PENDING = "PENDING"
    ANSWERED = "ANSWERED"
    CANCELLED = "CANCELLED"


# Print Status
class PrintStatus(str, enum.Enum):
    PENDING = "PENDING"
    PRINTING = "PRINTING"
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"
    RETRY = "RETRY"



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



class AuditAction(str, enum.Enum):
    """Ações de auditoria do sistema"""

    # ═══════════════════════════════════════════════════════════════════════════
    # PRODUTOS
    # ═══════════════════════════════════════════════════════════════════════════
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

    # ═══════════════════════════════════════════════════════════════════════════
    # CATEGORIAS ✅ EXPANDIDO
    # ═══════════════════════════════════════════════════════════════════════════
    CREATE_CATEGORY = "create_category"
    UPDATE_CATEGORY = "update_category"
    DELETE_CATEGORY = "delete_category"
    ACTIVATE_CATEGORY = "activate_category"  # ✅ NOVO
    DEACTIVATE_CATEGORY = "deactivate_category"  # ✅ NOVO
    REORDER_CATEGORIES = "reorder_categories"

    # Grupos de Opções (Option Groups)
    CREATE_OPTION_GROUP = "create_option_group"  # ✅ NOVO
    UPDATE_OPTION_GROUP = "update_option_group"  # ✅ NOVO
    DELETE_OPTION_GROUP = "delete_option_group"  # ✅ NOVO

    # Itens de Opções (Option Items)
    CREATE_OPTION_ITEM = "create_option_item"  # ✅ NOVO
    UPDATE_OPTION_ITEM = "update_option_item"  # ✅ NOVO
    DELETE_OPTION_ITEM = "delete_option_item"  # ✅ NOVO
    UPLOAD_OPTION_ITEM_IMAGE = "upload_option_item_image"  # ✅ NOVO

    # ═══════════════════════════════════════════════════════════════════════════
    # VARIANTES/COMPLEMENTOS
    # ═══════════════════════════════════════════════════════════════════════════
    CREATE_VARIANT = "create_variant"
    UPDATE_VARIANT = "update_variant"
    DELETE_VARIANT = "delete_variant"
    LINK_VARIANT_TO_PRODUCT = "link_variant_to_product"
    UNLINK_VARIANT_FROM_PRODUCT = "unlink_variant_from_product"
    BULK_UPDATE_VARIANT_STATUS = "bulk_update_variant_status"  # ✅ NOVO
    BULK_UNLINK_VARIANTS = "bulk_unlink_variants"  # ✅ NOVO

    # ═══════════════════════════════════════════════════════════════════════════
    # PEDIDOS ✅ EXPANDIDO
    # ═══════════════════════════════════════════════════════════════════════════
    CREATE_ORDER = "create_order"
    UPDATE_ORDER = "update_order"  # ✅ NOVO
    UPDATE_ORDER_STATUS = "update_order_status"
    CANCEL_ORDER = "cancel_order"
    REFUND_ORDER = "refund_order"  # ✅ NOVO
    APPLY_DISCOUNT = "apply_discount"
    REMOVE_DISCOUNT = "remove_discount"  # ✅ NOVO
    ADD_ITEM_TO_ORDER = "add_item_to_order"  # ✅ NOVO
    REMOVE_ITEM_FROM_ORDER = "remove_item_from_order"  # ✅ NOVO
    UPDATE_ORDER_ITEM_QUANTITY = "update_order_item_quantity"  # ✅ NOVO
    UPDATE_ORDER_PAYMENT_METHOD = "update_order_payment_method"  # ✅ NOVO
    MARK_ORDER_AS_PAID = "mark_order_as_paid"  # ✅ NOVO
    SPLIT_ORDER_PAYMENT = "split_order_payment"  # ✅ NOVO
    RETRY_ORDER_PAYMENT = "retry_order_payment"  # ✅ NOVO

    # ═══════════════════════════════════════════════════════════════════════════
    # CUPONS
    # ═══════════════════════════════════════════════════════════════════════════
    CREATE_COUPON = "create_coupon"
    UPDATE_COUPON = "update_coupon"
    DELETE_COUPON = "delete_coupon"
    ACTIVATE_COUPON = "activate_coupon"
    DEACTIVATE_COUPON = "deactivate_coupon"

    # ═══════════════════════════════════════════════════════════════════════════
    # ACESSOS E PERMISSÕES
    # ═══════════════════════════════════════════════════════════════════════════
    GRANT_STORE_ACCESS = "grant_store_access"
    REVOKE_STORE_ACCESS = "revoke_store_access"
    UPDATE_USER_ROLE = "update_user_role"

    # ═══════════════════════════════════════════════════════════════════════════
    # LOJAS
    # ═══════════════════════════════════════════════════════════════════════════
    CREATE_STORE = "create_store"
    UPDATE_STORE_SETTINGS = "update_store_settings"
    UPDATE_OPERATION_CONFIG = "update_operation_config"
    UPDATE_THEME = "update_theme"
    UPDATE_PAYMENT_METHODS = "update_payment_methods"

    # ═══════════════════════════════════════════════════════════════════════════
    # ASSINATURAS (BILLING)
    # ═══════════════════════════════════════════════════════════════════════════
    CREATE_SUBSCRIPTION = "create_subscription"
    REACTIVATE_SUBSCRIPTION = "reactivate_subscription"
    UPDATE_SUBSCRIPTION_CARD = "update_subscription_card"
    CANCEL_SUBSCRIPTION = "cancel_subscription"
    SUBSCRIPTION_PAYMENT_SUCCESS = "subscription_payment_success"
    SUBSCRIPTION_PAYMENT_FAILED = "subscription_payment_failed"

    # ═══════════════════════════════════════════════════════════════════════════
    # FINANCEIRO - CAIXA
    # ═══════════════════════════════════════════════════════════════════════════
    OPEN_CASHIER = "open_cashier"
    CLOSE_CASHIER = "close_cashier"
    ADD_CASH = "add_cash"
    REMOVE_CASH = "remove_cash"
    CASHIER_ADJUSTMENT = "cashier_adjustment"
    CASHIER_DISCREPANCY = "cashier_discrepancy"

    # ═══════════════════════════════════════════════════════════════════════════
    # FINANCEIRO - CONTAS
    # ═══════════════════════════════════════════════════════════════════════════
    CREATE_PAYABLE = "create_payable"
    UPDATE_PAYABLE = "update_payable"
    DELETE_PAYABLE = "delete_payable"
    PAY_PAYABLE = "pay_payable"

    # ═══════════════════════════════════════════════════════════════════════════
    # FORMAS DE PAGAMENTO
    # ═══════════════════════════════════════════════════════════════════════════
    ACTIVATE_PAYMENT_METHOD = "activate_payment_method"
    DEACTIVATE_PAYMENT_METHOD = "deactivate_payment_method"
    UPDATE_PAYMENT_METHOD_FEE = "update_payment_method_fee"
    UPDATE_PAYMENT_METHOD_CONFIG = "update_payment_method_config"

    # ═══════════════════════════════════════════════════════════════════════════
    # MESAS E COMANDAS ✅ EXPANDIDO
    # ═══════════════════════════════════════════════════════════════════════════
    CREATE_TABLE = "create_table"
    UPDATE_TABLE = "update_table"  # ✅ NOVO
    UPDATE_TABLE_STATUS = "update_table_status"
    DELETE_TABLE = "delete_table"
    OPEN_TABLE = "open_table"  # ✅ NOVO
    CLOSE_TABLE = "close_table"  # ✅ NOVO

    CREATE_COMMAND = "create_command"
    CLOSE_COMMAND = "close_command"
    ADD_ITEM_TO_COMMAND = "add_item_to_command"  # ✅ NOVO
    REMOVE_ITEM_FROM_COMMAND = "remove_item_from_command"  # ✅ NOVO
    TRANSFER_COMMAND = "transfer_command"  # ✅ NOVO
    MERGE_COMMANDS = "merge_commands"  # ✅ NOVO

    # ═══════════════════════════════════════════════════════════════════════════
    # CLIENTES
    # ═══════════════════════════════════════════════════════════════════════════
    CREATE_CUSTOMER = "create_customer"
    UPDATE_CUSTOMER = "update_customer"
    DELETE_CUSTOMER = "delete_customer"

    # ═══════════════════════════════════════════════════════════════════════════
    # SISTEMA
    # ═══════════════════════════════════════════════════════════════════════════
    LOGIN = "login"
    LOGOUT = "logout"
    FAILED_LOGIN = "failed_login"
    PASSWORD_CHANGE = "password_change"
    DATA_EXPORT = "data_export"
    DATA_IMPORT = "data_import"


class AuditEntityType(str, enum.Enum):
    """Tipos de entidades que podem ser auditadas"""

    # ═══════════════════════════════════════════════════════════════════════════
    # ENTIDADES PRINCIPAIS
    # ═══════════════════════════════════════════════════════════════════════════
    PRODUCT = "product"
    CATEGORY = "category"
    OPTION_GROUP = "option_group"  # ✅ NOVO
    OPTION_ITEM = "option_item"  # ✅ NOVO
    VARIANT = "variant"
    ORDER = "order"
    ORDER_ITEM = "order_item"  # ✅ NOVO
    CUSTOMER = "customer"
    COUPON = "coupon"

    # ═══════════════════════════════════════════════════════════════════════════
    # ACESSOS E USUÁRIOS
    # ═══════════════════════════════════════════════════════════════════════════
    STORE_ACCESS = "store_access"
    USER = "user"

    # ═══════════════════════════════════════════════════════════════════════════
    # LOJA E CONFIGURAÇÕES
    # ═══════════════════════════════════════════════════════════════════════════
    STORE = "store"
    STORE_SETTINGS = "store_settings"

    # ═══════════════════════════════════════════════════════════════════════════
    # FINANCEIRO
    # ═══════════════════════════════════════════════════════════════════════════
    SUBSCRIPTION = "subscription"
    PAYMENT_METHOD = "payment_method"
    CASHIER_SESSION = "cashier_session"
    CASHIER_TRANSACTION = "cashier_transaction"
    PAYABLE = "payable"

    # ═══════════════════════════════════════════════════════════════════════════
    # OPERAÇÃO
    # ═══════════════════════════════════════════════════════════════════════════
    TABLE = "table"
    COMMAND = "command"
    CART = "cart"


