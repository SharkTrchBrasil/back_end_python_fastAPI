# src/api/scheduler.py
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from src.api.jobs.billing import generate_monthly_charges
from src.api.jobs.cart_recovery import find_and_notify_abandoned_carts
from src.api.jobs.cleanup import delete_old_inactive_carts
from src.api.jobs.marketing import reactivate_inactive_customers
from src.api.jobs.operational import cancel_old_pending_orders, check_for_stuck_orders, \
    request_reviews_for_delivered_orders, finalize_old_delivered_orders
from src.api.jobs.trial_management import check_and_process_expired_trials

# Cria uma instância do agendador. O fuso horário UTC é recomendado para servidores.
scheduler = AsyncIOScheduler(timezone="UTC")


def start_scheduler():
    """ Adiciona todos os jobs ao agendador e o inicia. """
    print("⚙️  Configurando e iniciando o agendador de tarefas...")

    # --- Jobs Operacionais (execução frequente) ---
    scheduler.add_job(cancel_old_pending_orders, 'interval', minutes=1, id='cancel_orders_job')
    scheduler.add_job(check_for_stuck_orders, 'interval', minutes=5, id='stuck_orders_job')
    scheduler.add_job(find_and_notify_abandoned_carts, 'interval', minutes=5, id='cart_recovery_job')
    scheduler.add_job(request_reviews_for_delivered_orders, 'interval', minutes=15, id='request_reviews_job')
    scheduler.add_job(finalize_old_delivered_orders, 'interval', hours=1, id='finalize_orders_job')

    # --- Jobs de Marketing e Limpeza (execução diária) ---
    scheduler.add_job(reactivate_inactive_customers, 'interval', hours=24, id='reactivation_job')
    scheduler.add_job(delete_old_inactive_carts, 'interval', hours=24, id='cleanup_job')

    scheduler.add_job(generate_monthly_charges, 'cron', day='1', hour='3', id='monthly_billing_job')

    scheduler.add_job(check_and_process_expired_trials, 'cron', hour='2', id='expired_trials_job')

    # Inicia o agendador
    scheduler.start()
    print("✅ Agendador iniciado com sucesso!")