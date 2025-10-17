# src/api/scheduler.py
"""
Sistema de Agendamento de Tarefas
==================================

Gerencia execução automatizada de jobs:
- ✅ Operacionais (pedidos, carrinhos)
- ✅ Marketing (reativação)
- ✅ Billing (cobrança mensal)
- ✅ Lifecycle (assinaturas) ← ATUALIZADO
- ✅ Expiration (assinaturas canceladas) ← NOVO

Autor: Sistema
Última atualização: 2025-01-17
"""

import logging
from datetime import datetime, timezone

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.events import EVENT_JOB_EXECUTED, EVENT_JOB_ERROR

from src.api.jobs.billing import generate_monthly_charges
from src.api.jobs.cart_recovery import find_and_notify_abandoned_carts
from src.api.jobs.cleanup import delete_old_inactive_carts
from src.api.jobs.lifecycle import manage_subscription_lifecycle
from src.api.jobs.subscription_expiration import process_expired_subscriptions  # ✅ NOVO
from src.api.jobs.marketing import reactivate_inactive_customers
from src.api.jobs.operational import (
    cancel_old_pending_orders,
    check_for_stuck_orders,
    request_reviews_for_delivered_orders,
    finalize_old_delivered_orders
)

logger = logging.getLogger(__name__)

# ✅ Cria scheduler com configuração robusta
scheduler = AsyncIOScheduler(
    timezone="UTC",
    job_defaults={
        'coalesce': True,  # ✅ Agrupa execuções perdidas
        'max_instances': 1,  # ✅ Impede execuções simultâneas do mesmo job
        'misfire_grace_time': 300  # ✅ 5 minutos de tolerância
    }
)


def job_listener(event):
    """
    ✅ OBSERVABILIDADE: Monitora execução de jobs

    Loga sucessos e erros de todos os jobs agendados.
    """
    if event.exception:
        logger.error("job_failed", extra={
            "job_id": event.job_id,
            "scheduled_time": event.scheduled_run_time.isoformat() if event.scheduled_run_time else None,
            "error": str(event.exception),
            "traceback": event.traceback
        }, exc_info=True)
    else:
        logger.info("job_completed", extra={
            "job_id": event.job_id,
            "scheduled_time": event.scheduled_run_time.isoformat() if event.scheduled_run_time else None,
            "execution_time": datetime.now(timezone.utc).isoformat()
        })


def start_scheduler():
    """
    ✅ INICIALIZA: Configura e inicia todos os jobs agendados
    """
    logger.info("⚙️  Configurando e iniciando o agendador de tarefas...")

    # ✅ ADICIONA LISTENER PARA MONITORAMENTO
    scheduler.add_listener(job_listener, EVENT_JOB_EXECUTED | EVENT_JOB_ERROR)

    # ═══════════════════════════════════════════════════════════
    # JOBS OPERACIONAIS (Alta Frequência)
    # ═══════════════════════════════════════════════════════════

    # ✅ Cancela pedidos pendentes antigos (a cada 1 minuto)
    scheduler.add_job(
        cancel_old_pending_orders,
        'interval',
        minutes=1,
        id='cancel_orders_job',
        name='Cancelar Pedidos Pendentes Antigos'
    )

    # ✅ Verifica pedidos travados (a cada 5 minutos)
    scheduler.add_job(
        check_for_stuck_orders,
        'interval',
        minutes=5,
        id='stuck_orders_job',
        name='Verificar Pedidos Travados'
    )

    # ✅ Recuperação de carrinhos abandonados (a cada 5 minutos)
    scheduler.add_job(
        find_and_notify_abandoned_carts,
        'interval',
        minutes=5,
        id='cart_recovery_job',
        name='Recuperação de Carrinhos Abandonados'
    )

    # ✅ Solicita avaliações de pedidos entregues (a cada 15 minutos)
    scheduler.add_job(
        request_reviews_for_delivered_orders,
        'interval',
        minutes=15,
        id='request_reviews_job',
        name='Solicitar Avaliações'
    )

    # ✅ Finaliza pedidos entregues antigos (a cada 1 hora)
    scheduler.add_job(
        finalize_old_delivered_orders,
        'interval',
        hours=1,
        id='finalize_orders_job',
        name='Finalizar Pedidos Entregues'
    )

    # ═══════════════════════════════════════════════════════════
    # JOBS DIÁRIOS (Baixa Frequência)
    # ═══════════════════════════════════════════════════════════

    # ✅ Reativação de clientes inativos (todo dia às 10h UTC)
    scheduler.add_job(
        reactivate_inactive_customers,
        'cron',
        hour='10',
        id='reactivation_job',
        name='Reativação de Clientes Inativos'
    )

    # ✅ Limpeza de carrinhos antigos (todo dia às 4h UTC)
    scheduler.add_job(
        delete_old_inactive_carts,
        'cron',
        hour='4',
        id='cleanup_job',
        name='Limpeza de Carrinhos Antigos'
    )

    # ═══════════════════════════════════════════════════════════
    # JOBS MENSAIS/CRÍTICOS
    # ═══════════════════════════════════════════════════════════

    # ✅ BILLING: Roda TODO DIA útil às 3h
    scheduler.add_job(
        generate_monthly_charges,
        'cron',
        hour='3',
        minute='0',
        id='monthly_billing_job',
        name='Cobrança Mensal (verifica se é dia útil)'
    )

    # ✅ LIFECYCLE: Roda todo dia às 2h
    scheduler.add_job(
        manage_subscription_lifecycle,
        'cron',
        hour='2',
        minute='0',
        id='subscription_lifecycle_job',
        name='Gerenciamento de Ciclo de Assinaturas'
    )

    # ═══════════════════════════════════════════════════════════
    # ✅ NOVO: JOB DE EXPIRAÇÃO DE ASSINATURAS CANCELADAS
    # ═══════════════════════════════════════════════════════════

    # Roda todo dia às 00:05 (logo após meia-noite)
    # Processa assinaturas canceladas que expiraram no dia anterior
    scheduler.add_job(
        process_expired_subscriptions,
        'cron',
        hour='0',
        minute='5',
        id='subscription_expiration_job',
        name='Expiração de Assinaturas Canceladas (fecha loja e desconecta chatbot)'
    )

    # ═══════════════════════════════════════════════════════════
    # INICIA SCHEDULER
    # ═══════════════════════════════════════════════════════════

    scheduler.start()

    logger.info("✅ Agendador iniciado com sucesso!")
    logger.info("📋 Jobs configurados:", extra={
        "total_jobs": len(scheduler.get_jobs()),
        "jobs": [
            {
                "id": job.id,
                "name": job.name,
                "next_run": job.next_run_time.isoformat() if job.next_run_time else None
            }
            for job in scheduler.get_jobs()
        ]
    })


def stop_scheduler():
    """
    ✅ GRACEFUL SHUTDOWN: Para o scheduler de forma segura
    """
    if scheduler.running:
        logger.info("⏹️  Parando o agendador...")
        scheduler.shutdown(wait=True)
        logger.info("✅ Agendador parado com sucesso!")


def list_jobs():
    """
    ✅ UTILITÁRIO: Lista todos os jobs agendados (para debug/admin)

    Returns:
        Lista de dicionários com informações dos jobs
    """
    jobs = scheduler.get_jobs()

    jobs_info = []
    for job in jobs:
        jobs_info.append({
            "id": job.id,
            "name": job.name,
            "next_run": job.next_run_time.isoformat() if job.next_run_time else None,
            "trigger": str(job.trigger),
            "pending": job.pending
        })

    return jobs_info