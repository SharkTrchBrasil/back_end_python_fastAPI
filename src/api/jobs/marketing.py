# src/api/jobs/marketing.py
import httpx
from datetime import datetime, timedelta, timezone
from sqlalchemy import select, or_
from sqlalchemy.orm import selectinload

from src.api.admin.services.permission_service import store_has_feature
from src.core import models
from src.core.config import config

from src.core.database import get_db_manager

# --- Configurações da Campanha ---
INACTIVITY_DAYS = 60 # Cliente é considerado inativo após 60 dias
REACTIVATION_COOLDOWN_DAYS = 90 # Após uma tentativa, esperar 90 dias para tentar de novo
REACTIVATION_COUPON_CODE = "VOLTEMSEMPRE" # Código padrão do cupom que o lojista deve criar

async def reactivate_inactive_customers():
    """
    Encontra clientes inativos e envia uma mensagem de reativação com um cupom.
    """
    print("▶️  Executando job de reativação de clientes inativos...")
    now = datetime.now(timezone.utc)

    # Define as datas limite para a nossa busca
    inactivity_threshold = now - timedelta(days=INACTIVITY_DAYS)
    cooldown_threshold = now - timedelta(days=REACTIVATION_COOLDOWN_DAYS)

    with get_db_manager() as db:
        try:
            template = db.query(models.ChatbotMessageTemplate).filter_by(message_key='customer_reactivation').first()
            if not template:
                print("❌ ERRO: Template 'customer_reactivation' não encontrado.")
                return

            # 1. Busca TODAS as lojas ativas
            active_stores = db.query(models.Store).filter_by(is_active=True).all()

            for store in active_stores:
                # 2. ✅ O "PORTÃO" DE VERIFICAÇÃO DE FEATURE
                if not store_has_feature(db, store.id, 'inactive_customer_reactivation'):
                    print(f"  - Loja {store.id} ({store.name}) não tem a feature de reativação. Pulando.")
                    continue  # Pula para a próxima loja

                print(f"  - Verificando clientes inativos para a loja {store.id} ({store.name})...")

            stmt = (
                select(models.StoreCustomer)
                .options(
                    selectinload(models.StoreCustomer.customer),
                    selectinload(models.StoreCustomer.store)
                )
                .where(
                    models.StoreCustomer.last_order_at < inactivity_threshold,
                    or_(
                        models.StoreCustomer.last_reactivation_attempt_at == None,
                        models.StoreCustomer.last_reactivation_attempt_at < cooldown_threshold
                    )
                )
            )
            eligible_customers = db.execute(stmt).scalars().all()

            if not eligible_customers:
                print("✅ Nenhum cliente inativo para reativar hoje.")
                return

            print(f"💌 Encontrados {len(eligible_customers)} clientes inativos para reativar.")

            async with httpx.AsyncClient() as client:
                for sc in eligible_customers:
                    customer, store = sc.customer, sc.store
                    if not (customer and store and customer.phone and store.url_slug):
                        continue

                    # Busca o cupom padrão de reativação para esta loja
                    reactivation_coupon = db.query(models.Coupon).filter_by(
                        store_id=store.id,
                        code=REACTIVATION_COUPON_CODE,
                        is_active=True
                    ).first()

                    if not reactivation_coupon:
                        print(f"  - Aviso: Loja {store.id} não tem o cupom '{REACTIVATION_COUPON_CODE}' ativo. Pulando cliente {customer.id}.")
                        continue

                    # Monta a mensagem final
                    store_url = f"https://{store.url_slug}.{config.PLATFORM_DOMAIN}"
                    message_content = template.final_content
                    message_content = message_content.replace('{client.name}', customer.name.split(' ')[0])
                    message_content = message_content.replace('{store.name}', store.name)
                    message_content = message_content.replace('{coupon_code}', REACTIVATION_COUPON_CODE)
                    message_content = message_content.replace('{store.url}', store_url)

                    # Envia a mensagem via chatbot
                    payload = {"lojaId": str(store.id), "number": customer.phone, "message": message_content}
                    headers = {"x-webhook-secret": config.CHATBOT_WEBHOOK_SECRET}
                    response = await client.post(f"{config.CHATBOT_SERVICE_URL}/send-message", json=payload, headers=headers)

                    if response.status_code == 200:
                        print(f"  ✅ Mensagem de reativação para o cliente {customer.id} na loja {store.id} enviada.")
                        sc.last_reactivation_attempt_at = now
                    else:
                        print(f"  ❌ Falha ao enviar reativação para o cliente {customer.id}. Status: {response.status_code}")

            db.commit()

        except Exception as e:
            print(f"❌ ERRO CRÍTICO no job de reativação: {e}")
            db.rollback()