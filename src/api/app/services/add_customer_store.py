from datetime import datetime, timezone
from sqlalchemy.orm import Session
from src.core import models  # Ajuste conforme a estrutura real do projeto

def register_customer_store_relationship(db, store_id: int, customer_id: int, order_total: int):
    """
    Atualiza ou cria um relacionamento entre a loja e o cliente, acumulando pedidos e valor total gasto.
    """
    # 1. Verifica se o relacionamento entre loja e cliente já existe
    store_customer = db.query(models.StoreCustomer).filter_by(
        store_id=store_id,
        customer_id=customer_id
    ).first()

    now = datetime.now(timezone.utc)

    # 2. Atualiza se já existir
    if store_customer:
        store_customer.total_orders += 1
        store_customer.total_spent += order_total
        store_customer.last_order_at = now
    else:
        # 3. Cria se não existir
        store_customer = models.StoreCustomer(
            store_id=store_id,
            customer_id=customer_id,
            total_orders=1,
            total_spent=order_total,
            last_order_at=now
        )
        db.add(store_customer)

    db.commit()
