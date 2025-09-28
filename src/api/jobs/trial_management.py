# Arquivo: src/api/jobs/trial_management.py
# (Novo Arquivo)

from datetime import datetime, timezone, timedelta
from sqlalchemy import select
from src.core import models
from src.core.database import get_db_manager


def check_and_process_expired_trials():
    """
    Job diário que verifica assinaturas em trial que expiraram e as converte
    para o status 'active', iniciando o primeiro ciclo de cobrança.
    """
    print("▶️  Executando job de verificação de trials expirados...")
    today = datetime.now(timezone.utc)

    with get_db_manager() as db:
        try:
            # 1. Busca todas as assinaturas em trial que venceram (ontem ou antes)
            stmt = (
                select(models.StoreSubscription)
                .where(
                    models.StoreSubscription.status == 'trialing',
                    models.StoreSubscription.current_period_end < today
                )
            )
            expired_trials = db.execute(stmt).scalars().all()

            if not expired_trials:
                print("✅ Nenhum trial expirado para processar hoje.")
                return

            print(f"🔍 Encontrados {len(expired_trials)} trials expirados para converter.")

            for subscription in expired_trials:
                print(f"  - Convertendo trial da loja ID {subscription.store_id} para assinatura ativa.")

                # 2. Muda o status para 'active'
                subscription.status = 'active'

                # 3. Define o novo ciclo de faturamento
                # O primeiro ciclo de cobrança começa hoje e termina em 30 dias.
                subscription.current_period_start = today
                subscription.current_period_end = today + timedelta(days=30)

                # TODO (Opcional): Se a loja já tiver um cartão, você pode
                # tentar fazer a primeira cobrança aqui imediatamente.
                # Por agora, a cobrança será gerada normalmente no próximo dia 1º.

            db.commit()
            print("✅ Conversão de trials expirados concluída com sucesso.")

        except Exception as e:
            print(f"❌ ERRO CRÍTICO no job de gerenciamento de trials: {e}")
            db.rollback()