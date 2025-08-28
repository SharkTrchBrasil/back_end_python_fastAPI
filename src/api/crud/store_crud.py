from sqlalchemy.orm import Session, joinedload, selectinload, noload
from src.core import models

from sqlalchemy.orm import Session, joinedload, selectinload, noload
from src.core import models


def get_store_for_customer_view(db: Session, store_id: int) -> models.Store | None:
    """
    Consulta Otimizada para a Visão do Cliente (Cardápio/Totem).
    Atualizada para a relação muitos-para-muitos entre produtos e categorias.
    """
    store = (
        db.query(models.Store)
        .options(
            # --- Seções que não mudam ---
            joinedload(models.Store.segment),
            joinedload(models.Store.theme),
            joinedload(models.Store.store_operation_config),
            selectinload(models.Store.hours),
            selectinload(models.Store.scheduled_pauses),
            selectinload(models.Store.banners),
            selectinload(models.Store.coupons).selectinload(models.Coupon.rules),
            selectinload(models.Store.cities).selectinload(models.StoreCity.neighborhoods),
            selectinload(models.Store.payment_activations)
            .selectinload(models.StorePaymentMethodActivation.platform_method)
            .selectinload(models.PlatformPaymentMethod.category)
            .selectinload(models.PaymentMethodCategory.group),

            # ✅ CORREÇÃO PRINCIPAL AQUI: Carregamento do Cardápio Completo
            selectinload(models.Store.categories)
            .selectinload(models.Category.product_links)  # Passo 1: Da Categoria para a Tabela de Vínculo
            .selectinload(models.ProductCategoryLink.product)  # Passo 2: Do Vínculo para o Produto
            .options(  # Passo 3: A partir do Produto, carrega o resto como antes
                selectinload(models.Product.variant_links)
                .joinedload(models.ProductVariantLink.variant)
                .selectinload(models.Variant.options)
                .joinedload(models.VariantOption.linked_product),
                selectinload(models.Product.default_options)
                .joinedload(models.ProductDefaultOption.option),
            ),

            # Carregar os templates de complementos da loja (não muda)
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
            selectinload(models.Store.payment_activations)
                .selectinload(models.StorePaymentMethodActivation.platform_method)
                .selectinload(models.PlatformPaymentMethod.category)
                .selectinload(models.PaymentMethodCategory.group),
            selectinload(models.Store.subscriptions).joinedload(models.StoreSubscription.plan),
            selectinload(models.Store.coupons).selectinload(models.Coupon.rules),

            # ✅ CORREÇÃO: Adicione estas linhas para BARRAR o carregamento das listas pesadas
            noload(models.Store.products),
            noload(models.Store.categories),
            noload(models.Store.variants),

            noload(models.Store.orders)
        )
        .filter(models.Store.id == store_id)
        .first()
    )
    return store