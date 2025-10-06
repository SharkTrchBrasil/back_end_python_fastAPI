from sqlalchemy.orm import Session
from src.core import models


def clone_store_data(db: Session, source_store_id: int, new_store_id: int, options: dict):
    """
    Serviço central para clonar dados de uma loja de origem para uma nova.
    """
    print(f"Iniciando clonagem da loja {source_store_id} para {new_store_id} com opções: {options}")

    if options.get('theme', False):
        _clone_theme(db, source_store_id, new_store_id)

    if options.get('operation_config', False):
        _clone_operation_config(db, source_store_id, new_store_id)

    if options.get('payment_methods', False):
        _clone_payment_methods(db, source_store_id, new_store_id)

    # A clonagem de produtos e categorias é mais complexa
    if options.get('categories', False) or options.get('products', False):
        _clone_catalog(db, source_store_id, new_store_id, options)

    print("Clonagem concluída.")
    db.flush()


def _clone_theme(db: Session, source_id: int, new_id: int):
    print("Clonando tema...")
    source_theme = db.query(models.StoreTheme).filter_by(store_id=source_id).first()
    if source_theme:
        new_theme = models.StoreTheme(
            store_id=new_id,
            primary_color=source_theme.primary_color,
            mode=source_theme.mode,
            font_family=source_theme.font_family,
            theme_name=source_theme.theme_name
        )
        db.add(new_theme)


def _clone_operation_config(db: Session, source_id: int, new_id: int):
    print("Clonando configurações de operação...")
    source_config = db.query(models.StoreOperationConfig).filter_by(store_id=source_id).first()
    if source_config:
        new_config = models.StoreOperationConfig(
            store_id=new_id,
            # Copia todos os campos relevantes
            is_store_open=source_config.is_store_open,
            auto_accept_orders=source_config.auto_accept_orders,
            auto_print_orders=source_config.auto_print_orders,
            delivery_enabled=source_config.delivery_enabled,
            pickup_enabled=source_config.pickup_enabled,
            table_enabled=source_config.table_enabled,
            # ... copie todos os outros campos que fizerem sentido
        )
        db.add(new_config)


def _clone_payment_methods(db: Session, source_id: int, new_id: int):
    print("Clonando formas de pagamento...")
    source_payments = db.query(models.StorePaymentMethodActivation).filter_by(store_id=source_id, is_active=True).all()
    for payment in source_payments:
        new_payment = models.StorePaymentMethodActivation(
            store_id=new_id,
            platform_payment_method_id=payment.platform_payment_method_id,
            is_active=True,
            fee_percentage=payment.fee_percentage,
            details=payment.details,
            is_for_delivery=payment.is_for_delivery,
            is_for_pickup=payment.is_for_pickup,
            is_for_in_store=payment.is_for_in_store
        )
        db.add(new_payment)


def _clone_catalog(db: Session, source_id: int, new_id: int, options: dict):
    """Clona categorias e, opcionalmente, produtos."""
    print("Clonando catálogo...")

    # Mapeamento de IDs antigos para novos (essencial)
    category_id_map = {}
    product_id_map = {}

    # ✅ LÓGICA REFINADA: Se vamos clonar produtos, PRECISAMOS clonar as categorias primeiro.
    clone_categories_flag = options.get('categories', False) or options.get('products', False)

    # 1. Clonar Categorias (se necessário)
    if clone_categories_flag:
        print("Clonando categorias...")
        source_categories = db.query(models.Category).filter_by(store_id=source_id).all()
        for source_cat in source_categories:
            new_cat = models.Category(
                store_id=new_id,
                name=source_cat.name,
                priority=source_cat.priority,
                is_active=source_cat.is_active,
                type=source_cat.type,
                # ... copie outros campos da categoria, como 'pricing_strategy', 'price_varies_by_size', etc.
                pricing_strategy=source_cat.pricing_strategy,
                price_varies_by_size=source_cat.price_varies_by_size,
                selected_template=source_cat.selected_template,
            )
            db.add(new_cat)
            db.flush()
            category_id_map[source_cat.id] = new_cat.id
        print(f"{len(category_id_map)} categorias clonadas.")

    # 2. Clonar Produtos (se a opção estiver marcada)
    if options.get('products', False):
        print("Clonando produtos...")
        source_products = db.query(models.Product).filter_by(store_id=source_id).all()
        for source_prod in source_products:
            new_prod = models.Product(
                store_id=new_id,
                name=source_prod.name,
                description=source_prod.description,
                status=source_prod.status,
                priority=source_prod.priority,
                featured=source_prod.featured,
                # ... copie outros campos do produto
            )
            db.add(new_prod)
            db.flush()
            product_id_map[source_prod.id] = new_prod.id

            # 3. Linkar o novo produto às novas categorias
            for link in source_prod.category_links:
                if link.category_id in category_id_map:
                    new_category_id = category_id_map[link.category_id]
                    new_link = models.ProductCategoryLink(
                        product_id=new_prod.id,
                        category_id=new_category_id,
                        price=link.price,
                        is_available=link.is_available,
                        # ... copie outros campos do link
                        cost_price=link.cost_price,
                        is_on_promotion=link.is_on_promotion,
                        promotional_price=link.promotional_price,
                        display_order=link.display_order
                    )
                    db.add(new_link)
        print(f"{len(product_id_map)} produtos clonados e linkados.")