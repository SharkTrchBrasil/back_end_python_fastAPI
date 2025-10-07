# src/api/services/coupon_notification_service.py

import asyncio
import random
import httpx
from datetime import datetime, timezone

from sqlalchemy.orm import Session
from src.core import models
from src.core.config import config


async def send_coupon_notification_task(db: Session, coupon_id: int, store_id: int):
    """
    Tarefa de background para enviar notificações de um novo cupom para todos os clientes de uma loja.
    """
    print(f"🚀 Iniciando tarefa de notificação para o cupom {coupon_id} da loja {store_id}.")

    coupon = db.query(models.Coupon).filter_by(id=coupon_id, store_id=store_id).first()
    if not coupon:
        print(f"❌ ERRO: Cupom {coupon_id} não encontrado para a tarefa de notificação.")
        return

    # Pega o template da mensagem (Crie este template no seu banco de dados)
    template = db.query(models.ChatbotMessageTemplate).filter_by(message_key='new_coupon_notification').first()
    if not template:
        print(f"❌ ERRO: Template de mensagem 'new_coupon_notification' não encontrado.")
        coupon.whatsapp_notification_status = 'failed'
        db.commit()
        return

    # Busca todos os clientes associados à loja que têm um número de telefone válido
    store_customers = db.query(models.StoreCustomer).filter(
        models.StoreCustomer.store_id == store_id
    ).join(models.Customer).filter(models.Customer.phone != None).all()

    if not store_customers:
        print(f"✅ Nenhuma cliente com telefone encontrado para a loja {store_id}. Tarefa concluída.")
        coupon.whatsapp_notification_status = 'sent'  # Marcamos como enviado pois não há para quem enviar
        coupon.whatsapp_notification_sent_at = datetime.now(timezone.utc)
        db.commit()
        return

    # Atualiza o status para 'sending'
    coupon.whatsapp_notification_status = 'sending'
    db.commit()

    total_sent = 0
    total_failed = 0

    async with httpx.AsyncClient() as client:
        for sc in store_customers:
            customer = sc.customer
            store = sc.store

            # Monta a mensagem final
            store_url = f"https://{store.url_slug}.{config.PLATFORM_DOMAIN}"
            message_content = template.default_content  # Ou final_content se você tiver customização
            message_content = message_content.replace('{customer.name}', customer.name.split(' ')[0])
            message_content = message_content.replace('{store.name}', store.name)
            message_content = message_content.replace('{coupon.code}', coupon.code)
            message_content = message_content.replace('{coupon.description}', coupon.description)
            message_content = message_content.replace('{store.url}', store_url)

            # Envia a mensagem via serviço de chatbot
            payload = {"storeId": str(store.id), "number": customer.phone, "message": message_content}
            headers = {"x-webhook-secret": config.CHATBOT_WEBHOOK_SECRET}

            try:
                response = await client.post(f"{config.CHATBOT_SERVICE_URL}/send-message", json=payload,
                                             headers=headers, timeout=20.0)
                if response.status_code == 200:
                    total_sent += 1
                else:
                    total_failed += 1
            except httpx.RequestError as e:
                print(f"❌ Falha de comunicação ao enviar para {customer.phone}: {e}")
                total_failed += 1

            # ✅ A PARTE MAIS IMPORTANTE: Pausa aleatória para evitar bloqueio
            sleep_time = random.uniform(7, 20)  # Pausa entre 7 e 20 segundos
            await asyncio.sleep(sleep_time)

    # Finaliza a tarefa atualizando o status final no cupom
    coupon.whatsapp_notification_status = 'sent' if total_failed == 0 else 'partial_failure'
    coupon.whatsapp_notification_sent_at = datetime.now(timezone.utc)
    db.commit()

    print(
        f"✅ Tarefa de notificação para o cupom {coupon_id} concluída. Enviadas: {total_sent}, Falhas: {total_failed}.")