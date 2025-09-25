# src/api/scheduler.py
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from src.api.jobs.billing import check_and_update_subscriptions
from src.api.jobs.cart_recovery import find_and_notify_abandoned_carts
from src.api.jobs.cleanup import delete_old_inactive_carts
from src.api.jobs.marketing import reactivate_inactive_customers
from src.api.jobs.operational import cancel_old_pending_orders, check_for_stuck_orders, \
    request_reviews_for_delivered_orders

# Cria uma instância do agendador
scheduler = AsyncIOScheduler(timezone="UTC")


def start_scheduler():
    """ Adiciona todos os jobs ao agendador e o inicia. """
    print("⚙️  Configurando e iniciando o agendador de tarefas...")

    # Adiciona cada job com seu intervalo de execução
    scheduler.add_job(cancel_old_pending_orders, 'interval', minutes=1, id='cancel_orders_job')
    scheduler.add_job(check_for_stuck_orders, 'interval', minutes=5, id='stuck_orders_job')
    scheduler.add_job(check_and_update_subscriptions, 'interval', hours=1, id='subscriptions_job')
    scheduler.add_job(find_and_notify_abandoned_carts, 'interval', minutes=5, id='cart_recovery_job')
    scheduler.add_job(request_reviews_for_delivered_orders, 'interval', minutes=15, id='request_reviews_job')
    scheduler.add_job(reactivate_inactive_customers, 'interval', hours=24, id='reactivation_job')
    scheduler.add_job(delete_old_inactive_carts, 'interval', hours=24, id='cleanup_job')

    # Inicia o agendador
    scheduler.start()
    print("✅ Agendador iniciado com sucesso!")