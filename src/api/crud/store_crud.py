from sqlalchemy.orm import Session, joinedload, selectinload, noload
from src.core import models


def get_store_for_customer_view(db, store_id: int) -> models.Store | None:
    """
    Optimized Query for Customer View (Menu/Totem) com nova estrutura de categorias.
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
            .selectinload(models.PlatformPaymentMethod.group),

            # --- Full Menu/Catalog Loading ---
            selectinload(models.Store.categories)
            .selectinload(models.Category.product_links)
            .selectinload(models.ProductCategoryLink.product)
            .options(
                selectinload(models.Product.variant_links)
                .joinedload(models.ProductVariantLink.variant)
                .selectinload(models.Variant.options)
                .joinedload(models.VariantOption.linked_product),

                selectinload(models.Product.default_options)
                .joinedload(models.ProductDefaultOption.option),
            ),

            # --- Add-on templates (variantes soltas da loja) ---
            selectinload(models.Store.variants).selectinload(models.Variant.options),
        )
        .filter(models.Store.id == store_id)
        .first()
    )
    return store


def get_store_base_details(db, store_id: int) -> models.Store | None:
    """
    Consulta Otimizada: Carrega apenas os dados de configuração da loja.
    ✅ CORREÇÃO: Garante que store_operation_config seja carregado
    """
    store = (
        db.query(models.Store)
        .options(
            # --- Carrega apenas o essencial ---
            joinedload(models.Store.segment),
            joinedload(models.Store.theme),

            # ✅ CRÍTICO: Carrega a configuração operacional
            joinedload(models.Store.store_operation_config),

            selectinload(models.Store.hours),
            selectinload(models.Store.scheduled_pauses),
            selectinload(models.Store.banners),
            selectinload(models.Store.cities).selectinload(models.StoreCity.neighborhoods),

            selectinload(models.Store.payment_activations)
            .selectinload(models.StorePaymentMethodActivation.platform_method)
            .selectinload(models.PlatformPaymentMethod.group),

            selectinload(models.Store.subscriptions).joinedload(models.StoreSubscription.plan),

            selectinload(models.Store.coupons).selectinload(models.Coupon.rules),
            selectinload(models.Store.chatbot_messages).joinedload(models.StoreChatbotMessage.template),

            joinedload(models.Store.chatbot_config),

            selectinload(models.Store.monthly_charges).joinedload(models.MonthlyCharge.subscription),

            selectinload(models.Store.subscriptions)
            .joinedload(models.StoreSubscription.plan)
            .selectinload(models.Plans.included_features)
            .joinedload(models.PlansFeature.feature),
            selectinload(models.Store.print_layouts),

            noload(models.Store.products),
            noload(models.Store.categories),
            noload(models.Store.variants),
            noload(models.Store.orders)
        )
        .filter(models.Store.id == store_id)
        .first()
    )

    # ✅ LOG PARA DEBUG
    if store:
        if store.store_operation_config:
            print(f"✅ [CRUD] store_operation_config carregada: id={store.store_operation_config.id}")
        else:
            print(f"⚠️ [CRUD] store_operation_config É NULL para loja {store_id}")

        if store.subscriptions:
            print(f"✅ [CRUD] Loja {store_id} tem {len(store.subscriptions)} subscription(s)")
            print(f"   Status: {store.subscriptions[0].status if store.subscriptions else 'N/A'}")
        else:
            print(f"⚠️ [CRUD] Loja {store_id} SEM subscriptions carregadas!")
    else:
        print(f"❌ [CRUD] Loja {store_id} NÃO ENCONTRADA!")

    return store