# src/api/jobs/operational.py
import os
from datetime import datetime, timedelta, timezone

import httpx
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from src.core.config import config
from src.core.database import get_db_manager
from src.core import models
from src.core.utils.enums import OrderStatus  # Importe seu Enum de status
from src.api.admin.socketio.emitters import admin_emit_stuck_order_alert, admin_emit_order_updated_from_obj

# Define o tempo para considerar um pedido como "preso"
STUCK_ORDER_MINUTES = 20


async def check_for_stuck_orders():
    """
    Encontra pedidos no status 'preparing' há mais de 20 minutos
    E para os quais um alerta ainda não foi enviado.
    """
    print("▶️  Executando job de verificação de pedidos presos (Lógica Corrigida)...")

    now = datetime.now(timezone.utc)
    time_threshold = now - timedelta(minutes=STUCK_ORDER_MINUTES)

    with get_db_manager() as db:
        try:
            stmt = (
                select(models.Order)
                .where(
                    models.Order.order_status == OrderStatus.PREPARING,  # ✅ Usa o Enum direto
                    models.Order.updated_at < time_threshold,
                    models.Order.stuck_alert_sent_at == None
                )
            )
            stuck_orders = db.execute(stmt).scalars().all()

            if not stuck_orders:
                print("✅ Nenhum pedido preso novo para alertar.")
                return

            print(f"🔍 Encontrados {len(stuck_orders)} pedidos presos para alertar.")

            for order in stuck_orders:
                print(f"  - Enviando alerta para o pedido ID {order.id} ({order.public_id})")
                await admin_emit_stuck_order_alert(order)
                order.stuck_alert_sent_at = now

            db.commit()
            print("✅ Alertas de pedidos presos enviados com sucesso.")

        except Exception as e:
            print(f"❌ ERRO CRÍTICO no job de verificação de pedidos presos: {e}")


async def request_reviews_for_delivered_orders():
    """
    Encontra pedidos entregues recentemente e envia uma solicitação de avaliação.
    """
    print("▶️  Executando job de solicitação de avaliação...")

    now = datetime.now(timezone.utc)
    upper_threshold = now - timedelta(minutes=60)
    lower_threshold = now - timedelta(minutes=90)

    with get_db_manager() as db:
        try:
            template = db.query(models.ChatbotMessageTemplate).filter_by(message_key='request_review').first()
            if not template:
                print("❌ ERRO: Template 'request_review' não encontrado.")
                return

            stmt = (
                select(models.Order)
                .options(selectinload(models.Order.customer), selectinload(models.Order.store))
                .where(
                    models.Order.order_status == OrderStatus.DELIVERED,  # ✅ Usa o Enum direto
                    models.Order.review_request_sent_at == None,
                    models.Order.updated_at.between(lower_threshold, upper_threshold)
                )
            )
            eligible_orders = db.execute(stmt).scalars().all()

            if not eligible_orders:
                print("✅ Nenhum pedido elegível para solicitação de avaliação.")
                return

            print(f"💌 Encontrados {len(eligible_orders)} pedidos para solicitar avaliação.")

            async with httpx.AsyncClient() as client:
                for order in eligible_orders:
                    if not (order.customer and order.customer.phone and order.store):
                        continue

                    store_base_url = f"https://{order.store.url_slug}.{config.PLATFORM_DOMAIN}"
                    order_review_url = f"{store_base_url}/orders/{order.public_id}/review"

                    message_content = template.final_content
                    message_content = message_content.replace('{client.name}', order.customer.name.split(' ')[0])
                    message_content = message_content.replace('{company.name}', order.store.name)
                    message_content = message_content.replace('{order.url}', order_review_url)

                    payload = {"lojaId": str(order.store_id), "number": order.customer.phone, "message": message_content}
                    headers = {"x-webhook-secret": config.CHATBOT_WEBHOOK_SECRET}

                    response = await client.post(f"{config.CHATBOT_API_URL}/send-message", json=payload, headers=headers)

                    if response.status_code == 200:
                        print(f"  ✅ Solicitação de avaliação para o pedido {order.public_id} enviada.")
                        order.review_request_sent_at = now
                    else:
                        print(f"  ❌ Falha ao enviar solicitação para o pedido {order.public_id}. Status: {response.status_code}")

            db.commit()

        except Exception as e:
            print(f"❌ ERRO CRÍTICO no job de solicitação de avaliação: {e}")
            db.rollback()


async def cancel_old_pending_orders():
    """
    Encontra pedidos no status 'pending' com mais de 8 minutos
    e os cancela automaticamente, notificando o frontend.
    """
    print("▶️  Executando job de cancelamento automático de pedidos...")

    time_threshold = datetime.now(timezone.utc) - timedelta(minutes=8)

    with get_db_manager() as db:
        try:
            stmt = (
                select(models.Order)
                .where(
                    models.Order.order_status == OrderStatus.PENDING,  # ✅ Usa o Enum direto
                    models.Order.created_at < time_threshold
                )
            )
            orders_to_cancel = db.execute(stmt).scalars().all()

            if not orders_to_cancel:
                print("✅ Nenhum pedido pendente para cancelar.")
                return

            print(f"🔍 Encontrados {len(orders_to_cancel)} pedidos pendentes para cancelar.")

            for order in orders_to_cancel:
                print(f"  - Cancelando pedido ID {order.id} ({order.public_id}) por falta de aceite.")
                order.order_status = OrderStatus.CANCELED  # ✅ CORRIGIDO: Usa o Enum direto

                await admin_emit_order_updated_from_obj(order)

            db.commit()
            print(f"✅ Processamento de cancelamento concluído.")

        except Exception as e:
            print(f"❌ ERRO CRÍTICO no job de cancelamento de pedidos: {e}")
            db.rollback()


async def finalize_old_delivered_orders():
    """
    Encontra pedidos no status 'delivered' por mais de 4 horas
    e os move para 'finalized' automaticamente.
    """
    print("▶️  Executando job de finalização de pedidos antigos...")

    time_threshold = datetime.now(timezone.utc) - timedelta(hours=4)

    with get_db_manager() as db:
        try:
            stmt = (
                select(models.Order)
                .where(
                    models.Order.order_status == OrderStatus.DELIVERED,  # ✅ Usa o Enum direto
                    models.Order.updated_at < time_threshold
                )
            )

            orders_to_finalize = db.execute(stmt).scalars().all()

            if not orders_to_finalize:
                print("✅ Nenhum pedido entregue para finalizar.")
                return

            print(f"🔍 Encontrados {len(orders_to_finalize)} pedidos para finalizar.")

            for order in orders_to_finalize:
                print(f"  - Finalizando pedido ID {order.id} ({order.public_id}).")
                order.order_status = OrderStatus.FINALIZED  # ✅ CORRIGIDO: Usa o Enum direto

                await admin_emit_order_updated_from_obj(order)

            db.commit()
            print(f"✅ Processamento de finalização concluído.")

        except Exception as e:
            print(f"❌ ERRO CRÍTICO no job de finalização de pedidos: {e}")
            db.rollback()