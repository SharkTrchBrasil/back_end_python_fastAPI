# src/api/jobs/cart_recovery.py
import httpx
import os
from datetime import datetime, timedelta, timezone
from sqlalchemy.orm import selectinload
from sqlalchemy import select

from src.core.config import config
from src.core.database import get_db_manager
from src.core import models

# Define o tempo para considerar um carrinho como "abandonado"
ABANDONMENT_MINUTES = 30

async def find_and_notify_abandoned_carts():
    """
    Encontra carrinhos abandonados e dispara a notificação via API do chatbot.
    """
    print("▶️  Executando job de recuperação de carrinhos abandonados...")
    now = datetime.now(timezone.utc)
    abandonment_threshold = now - timedelta(minutes=ABANDONMENT_MINUTES)

    # O período de busca, ex: carrinhos atualizados entre 30 e 35 minutos atrás
    search_window_start = abandonment_threshold - timedelta(minutes=5)

    with get_db_manager() as db:
        try:
            # 1. Busca o template da mensagem de recuperação no banco
            template_query = select(models.ChatbotMessageTemplate).where(
                models.ChatbotMessageTemplate.message_key == 'abandoned_cart'
            )
            abandoned_cart_template = db.execute(template_query).scalar_one_or_none()

            if not abandoned_cart_template:
                print("❌ ERRO: Template 'abandoned_cart' não encontrado no banco de dados.")
                return

            # 2. Busca os carrinhos abandonados
            stmt = (
                select(models.Cart)
                .options(
                    selectinload(models.Cart.customer),
                    selectinload(models.Cart.store)
                )
                .join(models.Cart.items) # Garante que o carrinho não está vazio
                .where(
                    models.Cart.status == models.CartStatus.ACTIVE,
                    models.Cart.recovery_notified_at == None,
                    models.Cart.updated_at.between(search_window_start, abandonment_threshold)
                )
                .distinct()
            )
            abandoned_carts = db.execute(stmt).scalars().all()

            if not abandoned_carts:
                print("✅ Nenhum carrinho abandonado encontrado para notificar.")
                return

            print(f"🛒 Encontrados {len(abandoned_carts)} carrinhos para notificar.")

            async with httpx.AsyncClient() as client:
                for cart in abandoned_carts:
                    customer = cart.customer
                    store = cart.store

                    if not (customer and store and customer.phone):
                        continue

                    # 3. Monta a mensagem final
                    link_cardapio = f"https://{store.url_slug}.{config.PLATFORM_DOMAIN}" # Adapte para a sua estrutura de URL

                    message_content = abandoned_cart_template.default_content # Ou custom_content se houver
                    message_content = message_content.replace('{client.name}', customer.name.split(' ')[0])
                    message_content = message_content.replace('{company.url_products}', link_cardapio)

                    # 4. Dispara a API do Chatbot
                    payload = {
                        "lojaId": str(cart.store_id),
                        "number": customer.phone,
                        "message": message_content
                    }
                    headers = {
                        "x-webhook-secret": config.CHATBOT_WEBHOOK_SECRET
                    }

                    print(f"  -> Enviando notificação para o cliente {customer.id} da loja {cart.store_id}...")
                    response = await client.post(f"{config.CHATBOT_API_URL}/api/send-message", json=payload, headers=headers)

                    if response.status_code == 200:
                        print(f"  ✅ Notificação para o carrinho {cart.id} enviada com sucesso.")
                        cart.recovery_notified_at = now
                    else:
                        print(f"  ❌ Falha ao enviar notificação para o carrinho {cart.id}. Status: {response.status_code}, Resposta: {response.text}")

            db.commit()

        except Exception as e:
            print(f"❌ ERRO CRÍTICO no job de recuperação de carrinhos: {e}")
            db.rollback()