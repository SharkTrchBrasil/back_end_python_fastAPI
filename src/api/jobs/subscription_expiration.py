# src/api/jobs/subscription_expiration.py

"""
Job de Expiração de Assinaturas Canceladas
===========================================

Roda DIARIAMENTE para:
1. Verificar assinaturas canceladas que expiraram hoje
2. Desconectar chatbot
3. Fechar loja
4. Atualizar status para 'expired'
"""

import logging
from datetime import date, datetime, timezone
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from src.core import models
from src.core.database import get_db_manager

logger = logging.getLogger(__name__)


def process_expired_subscriptions():
    """
    ✅ PROCESSA ASSINATURAS CANCELADAS QUE EXPIRARAM HOJE

    Verifica:
    - Status = 'canceled'
    - current_period_end <= hoje

    Ações:
    - Desconecta chatbot
    - Fecha loja
    - Atualiza status para 'expired'
    """

    logger.info("═" * 60)
    logger.info("🔍 [Expiration Job] Iniciando verificação de assinaturas expiradas")
    logger.info("═" * 60)

    today = date.today()
    now = datetime.now(timezone.utc)

    with get_db_manager() as db:
        try:
            # ═══════════════════════════════════════════════════════════
            # 1. BUSCA ASSINATURAS CANCELADAS QUE EXPIRARAM
            # ═══════════════════════════════════════════════════════════

            expired_subscriptions = db.execute(
                select(models.StoreSubscription)
                .options(
                    selectinload(models.StoreSubscription.store)
                )
                .where(
                    models.StoreSubscription.status == 'canceled',
                    models.StoreSubscription.current_period_end <= now
                )
            ).scalars().all()

            total = len(expired_subscriptions)

            if total == 0:
                logger.info("✅ Nenhuma assinatura cancelada expirada hoje")
                return

            logger.info(f"📋 Encontradas {total} assinaturas para processar")

            # ═══════════════════════════════════════════════════════════
            # 2. PROCESSA CADA ASSINATURA
            # ═══════════════════════════════════════════════════════════

            success_count = 0
            error_count = 0

            for i, subscription in enumerate(expired_subscriptions, 1):
                store = subscription.store

                if not store:
                    logger.warning(f"⚠️ Assinatura {subscription.id} sem loja vinculada")
                    error_count += 1
                    continue

                logger.info(f"[{i}/{total}] Processando loja {store.id} ({store.name})")

                savepoint = db.begin_nested()

                try:
                    # ═══════════════════════════════════════════════════════════
                    # 2.1. DESCONECTA CHATBOT
                    # ═══════════════════════════════════════════════════════════

                    chatbot_config = db.query(models.StoreChatbotConfig).filter_by(
                        store_id=store.id
                    ).first()

                    if chatbot_config:
                        if chatbot_config.is_connected or chatbot_config.is_active:
                            chatbot_config.is_connected = False
                            chatbot_config.is_active = False
                            logger.info(f"  🤖 Chatbot desconectado para loja {store.id}")
                        else:
                            logger.info(f"  🤖 Chatbot já estava desconectado")
                    else:
                        logger.info(f"  🤖 Loja {store.id} não tem configuração de chatbot")

                    # ═══════════════════════════════════════════════════════════
                    # 2.2. FECHA LOJA
                    # ═══════════════════════════════════════════════════════════

                    operation_config = db.query(models.StoreOperationConfig).filter_by(
                        store_id=store.id
                    ).first()

                    if operation_config:
                        if operation_config.is_store_open:
                            operation_config.is_store_open = False
                            logger.info(f"  🔒 Loja {store.id} fechada automaticamente")
                        else:
                            logger.info(f"  🔒 Loja já estava fechada")
                    else:
                        logger.info(f"  🔒 Loja {store.id} não tem configuração de operação")

                    # ═══════════════════════════════════════════════════════════
                    # 2.3. ATUALIZA STATUS DA ASSINATURA
                    # ═══════════════════════════════════════════════════════════

                    old_status = subscription.status
                    subscription.status = 'expired'

                    logger.info(f"  📝 Status: {old_status} → expired")
                    logger.info(f"  📅 Cancelada em: {subscription.canceled_at.strftime('%d/%m/%Y')}")
                    logger.info(f"  📅 Expirada em: {subscription.current_period_end.strftime('%d/%m/%Y')}")

                    savepoint.commit()
                    success_count += 1

                    logger.info(f"  ✅ Loja {store.id} processada com sucesso")

                except Exception as e:
                    savepoint.rollback()
                    error_count += 1
                    logger.error(f"  ❌ Erro ao processar loja {store.id}: {e}", exc_info=True)

            # ═══════════════════════════════════════════════════════════
            # 3. COMMIT FINAL
            # ═══════════════════════════════════════════════════════════

            db.commit()

            logger.info("═" * 60)
            logger.info(f"✅ Job concluído: {success_count} sucesso, {error_count} erros")
            logger.info("═" * 60)

        except Exception as e:
            db.rollback()
            logger.error(f"❌ Erro crítico no job de expiração: {e}", exc_info=True)
            raise


if __name__ == "__main__":
    # Permite rodar manualmente para testes
    process_expired_subscriptions()