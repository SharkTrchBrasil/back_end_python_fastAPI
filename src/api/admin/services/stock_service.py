# Arquivo: src/services/stock_service.py
from sqlalchemy.orm import Session
from src.core import models

def decrease_stock_for_order(order: models.Order, db: Session):
    """
    Dá baixa no estoque para cada produto em um pedido.
    Esta função deve ser chamada quando um pedido é concluído.
    """
    print(f"Dando baixa no estoque para o pedido {order.id}...")
    for item in order.products:
        if item.product_id:
            # Busca o produto no banco para atualizar seu estoque
            product = db.query(models.Product).filter(models.Product.id == item.product_id).with_for_update().first()
            if product:
                # Supondo que seu modelo Product tenha uma coluna `stock_quantity`
                if product.stock_quantity >= item.quantity:
                    product.stock_quantity -= item.quantity
                else:
                    # Alerta importante: O estoque ficou negativo.
                    # Você pode querer lançar um erro ou apenas registrar um log.
                    print(f"ALERTA: Estoque para o produto '{product.name}' (ID: {product.id}) ficou negativo!")
                    product.stock_quantity -= item.quantity # Ou pode optar por não negativar e setar para 0
    print("Baixa de estoque concluída.")


def restock_for_canceled_order(order: models.Order, db: Session):
    """
    Retorna os itens de um pedido cancelado ao estoque.
    """
    print(f"Retornando itens do pedido cancelado {order.id} ao estoque...")
    for item in order.products:
        if item.product_id:
            product = db.query(models.Product).filter(models.Product.id == item.product_id).with_for_update().first()
            if product:
                # Adiciona a quantidade de volta ao estoque
                product.stock_quantity += item.quantity
    print("Retorno ao estoque concluído.")