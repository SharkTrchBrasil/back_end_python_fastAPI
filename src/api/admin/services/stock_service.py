# Arquivo: src/services/stock_service.py
from sqlalchemy.orm import Session, selectinload
from src.core import models
from src.core.utils.enums import ProductType  # Supondo que seu enum esteja aqui


def decrease_stock_for_order(order: models.Order, db: Session):
    """
    Dá baixa no estoque para cada produto em um pedido, considerando se é um
    produto individual (com variantes) ou um kit (com componentes).
    Esta função deve ser chamada quando um pedido é concluído.
    """
    print(f"📦 Iniciando baixa de estoque para o pedido {order.id}...")

    # Itera sobre cada item do pedido (objetos OrderProduct)
    for order_product in order.products:
        # Carregamos o produto e seus componentes de kit para saber como proceder
        product_master = db.query(models.Product).options(
            selectinload(models.Product.components).selectinload(models.KitComponent.component)
        ).filter(models.Product.id == order_product.product_id).first()

        if not product_master:
            print(f"ALERTA: Produto com ID {order_product.product_id} não encontrado no pedido {order.id}. Pulando.")
            continue

        order_quantity = order_product.quantity

        # --- CAMINHO 1: O PRODUTO É UM KIT/COMBO ---
        if product_master.product_type == ProductType.KIT:
            print(f"  -> Item é um Kit: '{product_master.name}'. Dando baixa nos componentes...")
            for component_link in product_master.components:
                component_product = db.query(models.Product).filter(
                    models.Product.id == component_link.component_product_id
                ).with_for_update().first()  # Trava o componente para atualização

                if component_product and component_product.control_stock:
                    quantity_to_decrease = component_link.quantity * order_quantity
                    component_product.stock_quantity -= quantity_to_decrease
                    print(
                        f"    - Componente '{component_product.name}': baixou {quantity_to_decrease} unidades. Novo estoque: {component_product.stock_quantity}")
            # Nota: O estoque do produto "Kit" em si não é alterado.

        # --- CAMINHO 2: O PRODUTO É INDIVIDUAL ---
        elif product_master.product_type == ProductType.PREPARED:
            print(f"  -> Item é Individual: '{product_master.name}'.")
            # 2a: Baixa no estoque do produto principal
            product_to_update = db.query(models.Product).filter(
                models.Product.id == product_master.id
            ).with_for_update().first()  # Trava o produto para atualização

            if product_to_update.control_stock:
                product_to_update.stock_quantity -= order_quantity
                print(
                    f"    - Produto principal: baixou {order_quantity} unidades. Novo estoque: {product_to_update.stock_quantity}")

            # 2b: Baixa no estoque das variantes (complementos)
            for order_variant in order_product.variants:
                for order_option in order_variant.options:
                    variant_option_master = db.query(models.VariantOption).filter(
                        models.VariantOption.id == order_option.variant_option_id
                    ).with_for_update().first()  # Trava a opção para atualização

                    if variant_option_master and variant_option_master.track_inventory:
                        quantity_to_decrease = order_option.quantity * order_quantity
                        variant_option_master.stock_quantity -= quantity_to_decrease
                        print(
                            f"      - Complemento '{variant_option_master.resolvedName}': baixou {quantity_to_decrease} unidades. Novo estoque: {variant_option_master.stock_quantity}")

    print("Baixa de estoque concluída.")


def restock_for_canceled_order(order: models.Order, db: Session):
    """
    Retorna os itens de um pedido cancelado ao estoque, considerando Kits e Variantes.
    """
    print(f"↩️ Retornando itens do pedido cancelado {order.id} ao estoque...")

    for order_product in order.products:
        product_master = db.query(models.Product).options(
            selectinload(models.Product.components).selectinload(models.KitComponent.component)
        ).filter(models.Product.id == order_product.product_id).first()

        if not product_master:
            continue

        order_quantity = order_product.quantity

        # --- LÓGICA DE DEVOLUÇÃO PARA KITS ---
        if product_master.product_type == ProductType.KIT:
            print(f"  -> Item é um Kit: '{product_master.name}'. Devolvendo componentes ao estoque...")
            for component_link in product_master.components:
                component_product = db.query(models.Product).filter(
                    models.Product.id == component_link.component_product_id
                ).with_for_update().first()

                if component_product and component_product.control_stock:
                    quantity_to_increase = component_link.quantity * order_quantity
                    component_product.stock_quantity += quantity_to_increase
                    print(
                        f"    - Componente '{component_product.name}': devolveu {quantity_to_increase} unidades. Novo estoque: {component_product.stock_quantity}")

        # --- LÓGICA DE DEVOLUÇÃO PARA PRODUTOS INDIVIDUAIS ---
        elif product_master.product_type == ProductType.PREPARED:
            print(f"  -> Item é Individual: '{product_master.name}'.")
            product_to_update = db.query(models.Product).filter(
                models.Product.id == product_master.id
            ).with_for_update().first()

            if product_to_update.control_stock:
                product_to_update.stock_quantity += order_quantity
                print(
                    f"    - Produto principal: devolveu {order_quantity} unidades. Novo estoque: {product_to_update.stock_quantity}")

            for order_variant in order_product.variants:
                for order_option in order_variant.options:
                    variant_option_master = db.query(models.VariantOption).filter(
                        models.VariantOption.id == order_option.variant_option_id
                    ).with_for_update().first()

                    if variant_option_master and variant_option_master.track_inventory:
                        quantity_to_increase = order_option.quantity * order_quantity
                        variant_option_master.stock_quantity += quantity_to_increase
                        print(
                            f"      - Complemento '{variant_option_master.resolvedName}': devolveu {quantity_to_increase} unidades. Novo estoque: {variant_option_master.stock_quantity}")

    print("Retorno ao estoque concluído.")