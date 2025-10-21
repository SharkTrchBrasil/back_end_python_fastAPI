"""
Monitoring & Health Check Endpoints
====================================
Endpoints para monitoramento de saúde e métricas do sistema

Autor: PDVix Team
"""
import time

from fastapi import APIRouter

from src.core import models
from src.core.cache.redis_client import redis_client
from src.core.database import get_pool_stats, check_database_health, GetDBDep
from src.core.dependencies import GetCurrentUserDep
from src.core.monitoring.metrics import metrics

router = APIRouter(prefix="/monitoring", tags=["Monitoring"])


@router.get("/health")
async def health_check():
    """
    🏥 Health check básico - PÚBLICO (sem autenticação)

    Usado por load balancers e monitoring tools
    """
    db_health = check_database_health()

    return {
        "status": "healthy" if db_health["healthy"] else "unhealthy",
        "timestamp": db_health["timestamp"],
        "services": {
            "database": "up" if db_health["healthy"] else "down",
            "redis": "up" if redis_client.is_available else "down",
        }
    }


@router.get("/health/detailed")
async def detailed_health_check(user: GetCurrentUserDep):
    """
    🔍 Health check detalhado - REQUER AUTENTICAÇÃO

    Retorna métricas completas do sistema
    """
    db_health = check_database_health()
    pool_stats = get_pool_stats()
    metrics_summary = metrics.get_metrics_summary()

    return {
        "status": "healthy" if db_health["healthy"] else "unhealthy",
        "timestamp": db_health["timestamp"],
        "database": {
            "health": db_health,
            "pool": pool_stats,
        },
        "cache": {
            "redis_available": redis_client.is_available,
            "redis_stats": redis_client.get_stats() if redis_client.is_available else None,
        },
        "metrics": metrics_summary,
    }


@router.get("/metrics")
async def get_metrics(user: GetCurrentUserDep):
    """
    📊 Endpoint de métricas - Formato Prometheus-compatible
    """
    return metrics.get_metrics_summary()


@router.get("/stats/stores")
async def get_store_stats(db: GetDBDep, user: GetCurrentUserDep):
    """
    🏪 Estatísticas de lojas
    """
    from sqlalchemy import func

    total_stores = db.query(func.count(models.Store.id)).scalar()
    active_stores = db.query(func.count(models.Store.id)).filter(
        models.Store.is_active == True
    ).scalar()

    # Lojas por status de verificação
    verification_stats = db.query(
        models.Store.verification_status,
        func.count(models.Store.id)
    ).group_by(models.Store.verification_status).all()

    # Lojas por status de assinatura
    subscription_stats = db.query(
        models.StoreSubscription.status,
        func.count(models.StoreSubscription.id)
    ).group_by(models.StoreSubscription.status).all()

    return {
        "total_stores": total_stores,
        "active_stores": active_stores,
        "inactive_stores": total_stores - active_stores,
        "verification_status": {status: count for status, count in verification_stats},
        "subscription_status": {status: count for status, count in subscription_stats},
    }


@router.get("/stats/performance")
async def get_performance_stats(user: GetCurrentUserDep):
    """
    ⚡ Estatísticas de performance
    """
    pool_stats = get_pool_stats()
    metrics_summary = metrics.get_metrics_summary()

    return {
        "database_pool": pool_stats,
        "request_metrics": metrics_summary["requests"],
        "database_metrics": metrics_summary["database"],
        "cache_metrics": metrics_summary["cache"],
    }


@router.post("/cache/clear")
async def clear_cache(user: GetCurrentUserDep):
    """
    🗑️ Limpa todo o cache - USE COM CUIDADO!
    """
    from src.core.cache.enterprise_cache import enterprise_cache

    enterprise_cache.clear_all()

    return {
        "message": "Cache limpo com sucesso",
        "timestamp": time.time()
    }


@router.get("/alerts")
async def get_system_alerts(user: GetCurrentUserDep):
    """
    🚨 Alertas do sistema
    """
    alerts = []

    # Verifica pool de conexões
    pool_stats = get_pool_stats()
    if pool_stats["utilization_percent"] > 80:
        alerts.append({
            "severity": "warning",
            "type": "database_pool",
            "message": f"Pool de conexões em {pool_stats['utilization_percent']}%",
            "recommendation": "Considere aumentar pool_size ou max_overflow"
        })

    # Verifica circuit breaker
    if pool_stats["circuit_breaker_state"] != "CLOSED":
        alerts.append({
            "severity": "critical",
            "type": "circuit_breaker",
            "message": f"Circuit breaker está {pool_stats['circuit_breaker_state']}",
            "recommendation": "Verifique logs de erro do banco de dados"
        })

    # Verifica Redis
    if not redis_client.is_available:
        alerts.append({
            "severity": "warning",
            "type": "cache",
            "message": "Redis não está disponível",
            "recommendation": "Sistema funcionando sem cache. Performance pode estar degradada."
        })

    # Verifica error rate
    metrics_summary = metrics.get_metrics_summary()
    error_rate = metrics_summary["requests"].get("error_rate", 0)
    if error_rate > 5:  # Mais de 5% de erro
        alerts.append({
            "severity": "warning",
            "type": "error_rate",
            "message": f"Taxa de erro em {error_rate}%",
            "recommendation": "Verifique logs de aplicação"
        })

    return {
        "alerts": alerts,
        "alert_count": len(alerts),
        "severity_counts": {
            "critical": sum(1 for a in alerts if a["severity"] == "critical"),
            "warning": sum(1 for a in alerts if a["severity"] == "warning"),
            "info": sum(1 for a in alerts if a["severity"] == "info"),
        }
    }