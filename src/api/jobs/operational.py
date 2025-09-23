# src/api/jobs/operational.py
from datetime import datetime, timedelta, timezone
from sqlalchemy import select

from src.core.database import get_db_manager
from src.core import models
from src.core.utils.enums import OrderStatus # Importe seu Enum de status
from src.api.admin.socketio.emitters import admin_emit_stuck_order_alert

# Define o tempo para considerar um pedido como "preso"
STUCK_ORDER_MINUTES = 20

async def check_for_stuck_orders():
    """
    Encontra pedidos no status 'accepted' por muito tempo e notifica o painel do lojista.
    """
    print("▶️  Executando job de verificação de pedidos presos...")

    # Para evitar enviar alertas repetidos, buscamos pedidos que entraram na
    # janela de "preso" desde a última verificação.
    # Ex: Se o job roda a cada 5 min, ele busca pedidos presos entre 20 e 25 minutos atrás.
    now = datetime.now(timezone.utc)
    upper_threshold = now - timedelta(minutes=STUCK_ORDER_MINUTES)
    lower_threshold = upper_threshold - timedelta(minutes=5) # Janela de 5 minutos

    with get_db_manager() as db:
        try:
            # 1. Monta a query para encontrar os pedidos presos na janela de tempo
            stmt = (
                select(models.Order)
                .where(
                    models.Order.order_status == OrderStatus,
                    models.Order.updated_at.between(lower_threshold, upper_threshold)
                )
            )

            stuck_orders = db.execute(stmt).scalars().all()

            if not stuck_orders:
                print("✅ Nenhum pedido preso encontrado.")
                return

            print(f"🔍 Encontrados {len(stuck_orders)} pedidos presos para alertar.")

            # 2. Itera sobre os pedidos e envia o alerta para cada um
            for order in stuck_orders:
                await admin_emit_stuck_order_alert(order)

        except Exception as e:
            print(f"❌ ERRO CRÍTICO no job de verificação de pedidos presos: {e}")