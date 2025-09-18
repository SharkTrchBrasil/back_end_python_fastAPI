# em services/table_service.py
from sqlalchemy.orm import Session

from src.api.schemas.store.table import AddItemToCommandSchema
from src.core import models
from src.core.database import GetDBDep


class TableService:
    def __init__(self, db: GetDBDep):
        self.db = db

    def add_item_to_table(self, table_id: int, item_data: AddItemToCommandSchema):
        # 1. Encontrar a mesa
        table = self.db.query(models.Table).filter(models.Table.id == table_id).first()
        if not table:
            raise Exception("Mesa não encontrada")

        # 2. Encontrar ou criar uma comanda ativa para a mesa
        # (Lógica simplificada: pega a primeira comanda ativa)
        command = self.db.query(models.Command).filter(
            models.Command.table_id == table_id,
            models.Command.status == 'ACTIVE'
        ).first()

        if not command:
            # Se não houver comanda, cria uma nova
            command = models.Command(store_id=table.store_id, table_id=table.id, status='ACTIVE')
            self.db.add(command)
            self.db.flush()  # Para pegar o ID da nova comanda

        # 3. Encontrar o produto para pegar o preço e nome
        product = self.db.query(models.Product).filter(models.Product.id == item_data.product_id).first()
        if not product:
            raise Exception("Produto não encontrado")

        # 4. Criar o pedido (Order) associado à comanda
        new_order = models.Order(
            store_id=table.store_id,
            command_id=command.id,
            table_id=table.id,
            # ... preencha outros campos do Order, como total_price, etc.
            # Este é um ponto crucial: você precisa calcular o preço total aqui
        )

        # 5. Criar o item do pedido (OrderProduct)
        order_product = models.OrderProduct(
            order=new_order,
            product_id=product.id,
            name=product.name,
            price=product.price,  # Assumindo que o preço está no produto
            quantity=item_data.quantity,
            note=item_data.notes
            # ... associar variantes aqui
        )

        self.db.add(new_order)
        self.db.add(order_product)

        # 6. Atualizar o status da mesa se necessário
        if table.status == 'AVAILABLE':
            table.status = 'OCCUPIED'

        self.db.commit()
        # Aqui, você retornaria o estado atualizado da mesa ou emitiria o evento WebSocket

        return table