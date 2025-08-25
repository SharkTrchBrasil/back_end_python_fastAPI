from sqlalchemy.orm import Session, joinedload, selectinload
from src.core import models




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
             selectinload(models.Store.coupons).selectinload(models.Coupon.rules)
        )
        .filter(models.Store.id == store_id)
        .first()
    )
    return store