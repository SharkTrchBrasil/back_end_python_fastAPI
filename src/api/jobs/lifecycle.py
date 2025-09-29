# Arquivo: src/api/jobs/lifecycle.py

from datetime import datetime, timezone, timedelta
from sqlalchemy import select
from src.core import models
from src.core.database import get_db_manager


def manage_subscription_lifecycle():
    """
    Job diário que gerencia o ciclo de vida das assinaturas.
    1. Expira trials que terminaram.
    2. Bloqueia contas com pagamento pendente após o período de carência.
    """
    print("▶️  Executando job de ciclo de vida das assinaturas...")
    today = datetime.now(timezone.utc)

    with get_db_manager() as db:
        try:
            # --- 1. Processa Trials que Terminaram ---
            stmt_trials = (
                select(models.StoreSubscription)
                .where(
                    models.StoreSubscription.status == 'trialing',
                    models.StoreSubscription.current_period_end < today
                )
            )
            expired_trials = db.execute(stmt_trials).scalars().all()

            if expired_trials:
                print(f"🔍 Encontrados {len(expired_trials)} trials que terminaram.")
                for subscription in expired_trials:
                    # ✅ CORREÇÃO CRÍTICA: O status muda para 'expired', não 'active'.
                    # Isso força o usuário a adicionar um cartão para continuar.
                    subscription.status = 'expired'
                    print(f"  - Trial da loja ID {subscription.store_id} finalizado. Status alterado para 'expired'.")
            else:
                print("✅ Nenhum trial para expirar hoje.")

            # --- 2. Processa Assinaturas com Pagamento Pendente (Dunning) ---
            grace_period_days = 5
            # Verifica assinaturas que estão 'past_due' há mais tempo que o período de carência
            grace_period_limit_date = today - timedelta(days=grace_period_days)

            stmt_past_due = (
                select(models.StoreSubscription).where(
                    models.StoreSubscription.status == 'past_due',
                    # updated_at é atualizado quando o status muda para past_due
                    models.StoreSubscription.updated_at < grace_period_limit_date
                )
            )
            past_due_subs = db.execute(stmt_past_due).scalars().all()

            if past_due_subs:
                print(f"🔍 Encontradas {len(past_due_subs)} assinaturas pendentes fora do período de carência.")
                for subscription in past_due_subs:
                    subscription.status = 'expired' # Bloqueia o acesso
                    print(f"  - Período de carência da loja ID {subscription.store_id} finalizado. Acesso bloqueado.")
            else:
                print("✅ Nenhuma assinatura pendente para bloquear hoje.")

            db.commit()
            print("✅ Job de ciclo de vida finalizado com sucesso.")

        except Exception as e:
            print(f"❌ ERRO CRÍTICO no job de ciclo de vida: {e}")
            db.rollback()