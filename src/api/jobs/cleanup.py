# src/api/jobs/cleanup.py
from datetime import datetime, timedelta, timezone
from sqlalchemy import delete

from src.core.database import get_db_manager
from src.core import models

# Define a idade máxima de um carrinho inativo antes de ser apagado
MAX_CART_AGE_DAYS = 15

def delete_old_inactive_carts():
    """
    Encontra e apaga carrinhos que estão inativos há mais de MAX_CART_AGE_DAYS
    e que não foram convertidos em um pedido.
    """
    print("▶️  Executando job de limpeza de carrinhos antigos...")
    now = datetime.now(timezone.utc)
    deletion_threshold = now - timedelta(days=MAX_CART_AGE_DAYS)

    with get_db_manager() as db:
        try:
            # 1. Monta a query para encontrar os carrinhos antigos e inativos
            # O critério principal é o status 'ACTIVE', pois não queremos apagar
            # carrinhos 'COMPLETED', que são o histórico de pedidos finalizados.
            stmt = (
                delete(models.Cart)
                .where(
                    models.Cart.status == models.CartStatus.ACTIVE,
                    models.Cart.updated_at < deletion_threshold
                )
            )

            # 2. Executa a deleção em massa
            result = db.execute(stmt)
            deleted_count = result.rowcount

            if deleted_count > 0:
                print(f"✅ Sucesso! {deleted_count} carrinhos antigos foram apagados.")
            else:
                print("✅ Nenhum carrinho antigo para apagar.")

            db.commit()

        except Exception as e:
            print(f"❌ ERRO CRÍTICO no job de limpeza de carrinhos: {e}")
            db.rollback()