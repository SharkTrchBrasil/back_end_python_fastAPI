from sqlalchemy.orm import Session, joinedload, selectinload
from src.core import models


def get_store_with_all_details(db: Session, store_id: int) -> models.Store | None:
    """
    A "Super Consulta": Carrega um objeto Store com ABSOLUTAMENTE TUDO.
    """
    store = (
        db.query(models.Store)
        .options(
            # --- Configurações Gerais e Estrutura da Loja ---
            joinedload(models.Store.segment),
            joinedload(models.Store.theme),
            joinedload(models.Store.store_operation_config),

            # --- Listas de Configurações ---
            selectinload(models.Store.hours),
            selectinload(models.Store.scheduled_pauses),
            selectinload(models.Store.banners),
            selectinload(models.Store.accesses).joinedload(models.StoreAccess.user),
            selectinload(models.Store.accesses).joinedload(models.StoreAccess.role),

            # --- Logística e Entrega ---
            selectinload(models.Store.cities).selectinload(models.StoreCity.neighborhoods),

            # --- Financeiro e Pagamentos ---
            selectinload(models.Store.payables),
            selectinload(models.Store.payment_activations)
                .selectinload(models.StorePaymentMethodActivation.platform_method)
                .selectinload(models.PlatformPaymentMethod.category)
                .selectinload(models.PaymentMethodCategory.group),

            # --- Assinatura e Plano (Completo) ---
            selectinload(models.Store.subscriptions)
                .joinedload(models.StoreSubscription.plan)
                .selectinload(models.Plans.included_features)
                .joinedload(models.PlansFeature.feature),
            selectinload(models.Store.subscriptions)
                .selectinload(models.StoreSubscription.subscribed_addons)
                .joinedload(models.PlansAddon.feature),

            # --- Gestão de Cardápio, Produtos e Categorias ---
            selectinload(models.Store.categories)
                .selectinload(models.Category.products)
                .options(
                    selectinload(models.Product.variant_links)
                        .joinedload(models.ProductVariantLink.variant)
                        .selectinload(models.Variant.options)
                        .joinedload(models.VariantOption.linked_product),
                    selectinload(models.Product.default_options)
                        .joinedload(models.ProductDefaultOption.option),
                ),

            # --- Gestão de Templates de Complementos ---
            selectinload(models.Store.variants).selectinload(models.Variant.options),

            # --- Operacional (Pedidos, Cupons, Clientes) ---
            # selectinload(models.Store.orders),  # Geralmente pesado demais para carregar sempre
            selectinload(models.Store.coupons).selectinload(models.Coupon.rules),
            selectinload(models.Store.commands),
            selectinload(models.Store.cashier_sessions),
            selectinload(models.Store.store_customers).joinedload(models.StoreCustomer.customer),
            selectinload(models.Store.store_ratings),
        )
        .filter(models.Store.id == store_id)
        .first()
    )
    return store


def get_store_with_operational_details(db: Session, store_id: int) -> models.Store | None:
    """
    Consulta Leve: Carrega dados operacionais essenciais.
    """
    store = (
        db.query(models.Store)
        .options(
            joinedload(models.Store.store_operation_config),
            selectinload(models.Store.hours),
            selectinload(models.Store.scheduled_pauses),
            selectinload(models.Store.cities).selectinload(models.StoreCity.neighborhoods),
            selectinload(models.Store.coupons).selectinload(models.Coupon.rules),
            selectinload(models.Store.subscriptions).joinedload(models.StoreSubscription.plan),
            selectinload(models.Store.payment_activations)
                .selectinload(models.StorePaymentMethodActivation.platform_method)
                .selectinload(models.PlatformPaymentMethod.category)
                .selectinload(models.PaymentMethodCategory.group),
        )
        .filter(models.Store.id == store_id)
        .first()
    )
    return store


def get_store_for_customer_view(db: Session, store_id: int) -> models.Store | None:
    """
    Optimized Query for Customer View (Menu/Totem).
    """
    store = (
        db.query(models.Store)
        .options(
            # --- Branding & Core Info ---
            joinedload(models.Store.segment),
            joinedload(models.Store.theme),

            # --- Operational Status ---
            joinedload(models.Store.store_operation_config),
            selectinload(models.Store.hours),
            selectinload(models.Store.scheduled_pauses),

            # --- Marketing & UI ---
            selectinload(models.Store.banners),
            selectinload(models.Store.coupons).selectinload(models.Coupon.rules),

            # --- Logistics ---
            selectinload(models.Store.cities).selectinload(models.StoreCity.neighborhoods),

            # --- Payment Methods ---
            selectinload(models.Store.payment_activations)
                .selectinload(models.StorePaymentMethodActivation.platform_method)
                .selectinload(models.PlatformPaymentMethod.category)
                .selectinload(models.PaymentMethodCategory.group),

            # --- Full Menu/Catalog Loading ---
            selectinload(models.Store.categories)
                .selectinload(models.Category.products)
                .options(
                    selectinload(models.Product.variant_links)
                        .joinedload(models.ProductVariantLink.variant)
                        .selectinload(models.Variant.options)
                        .joinedload(models.VariantOption.linked_product),
                    selectinload(models.Product.default_options)
                        .joinedload(models.ProductDefaultOption.option),
                ),

            # Path 2: Load all available add-on templates for the store.
            selectinload(models.Store.variants).selectinload(models.Variant.options),
        )
        .filter(models.Store.id == store_id)
        .first()
    )
    return store





def get_store_base_details(db: Session, store_id: int) -> models.Store | None:
    """
    Consulta Otimizada: Carrega apenas os dados de configuração da loja.
    (Exclui listas pesadas como produtos, categorias, clientes, etc.)
    """
    store = (
        db.query(models.Store)
        .options(
            # --- Carrega apenas o essencial ---
            joinedload(models.Store.segment),
            joinedload(models.Store.theme),
            joinedload(models.Store.store_operation_config),
            selectinload(models.Store.hours),
            selectinload(models.Store.scheduled_pauses),
            selectinload(models.Store.banners),
            selectinload(models.Store.cities).selectinload(models.StoreCity.neighborhoods),
            selectinload(models.Store.payment_activations) # Carregamento simplificado
                .selectinload(models.StorePaymentMethodActivation.platform_method)
                .selectinload(models.PlatformPaymentMethod.category)
                .selectinload(models.PaymentMethodCategory.group),
             selectinload(models.Store.subscriptions).joinedload(models.StoreSubscription.plan),
        )
        .filter(models.Store.id == store_id)
        .first()
    )
    return store