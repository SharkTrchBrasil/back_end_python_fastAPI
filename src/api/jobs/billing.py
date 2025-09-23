# src/api/jobs/billing.py
from datetime import datetime, timezone
from sqlalchemy import select

from src.api.admin.services.subscription_service import downgrade_to_free_plan
from src.core import models
from src.core.database import get_db_manager



def check_and_update_subscriptions():
    """
    Verifica assinaturas vencidas e realiza o downgrade para o plano gratuito se necessário.
    Atua como uma rede de segurança para webhooks perdidos.
    """
    print("▶️  Executando job de verificação de assinaturas vencidas...")
    now = datetime.now(timezone.utc)

    with get_db_manager() as db:
        try:
            # 1. Busca por assinaturas que estão ativas, mas cujo período de pagamento já terminou.
            #    Ignoramos planos gratuitos que já têm data de término longa.
            stmt = (
                select(models.StoreSubscription)
                .join(models.StoreSubscription.plan)
                .where(
                    models.StoreSubscription.status.in_(['active', 'new_charge']),
                    models.StoreSubscription.current_period_end < now,
                    models.Plans.price > 0
                )
            )

            expired_subscriptions = db.execute(stmt).scalars().all()

            if not expired_subscriptions:
                print("✅ Nenhuma assinatura vencida encontrada para processar.")
                return

            print(f"🔍 Encontradas {len(expired_subscriptions)} assinaturas vencidas para processar.")

            for sub in expired_subscriptions:
                print(f"  - Assinatura ID {sub.id} da loja {sub.store_id} está vencida. Processando downgrade...")
                # 2. Chama o serviço centralizado para fazer o downgrade
                downgrade_to_free_plan(db, sub)

            db.commit()
            print("✅ Processamento de assinaturas vencidas concluído.")

        except Exception as e:
            print(f"❌ ERRO CRÍTICO no job de verificação de assinaturas: {e}")
            db.rollback()