import math
from datetime import datetime, timedelta, timezone
from typing import Optional, Literal

from fastapi import APIRouter, Query, HTTPException, Path
from sqlalchemy import func, desc, and_
from sqlalchemy.orm import joinedload

from src.api.schemas.audit.audit import AuditLogListResponse, AuditLogDetailResponse, EntityChangeHistory, \
    AuditStatistics
from src.core import models
from src.core.database import GetDBDep
from src.core.dependencies import GetStoreDep, GetCurrentUserDep
from src.core.utils.enums import AuditAction, AuditEntityType

router = APIRouter(prefix="/stores/{store_id}/audit", tags=["Audit Logs"])


# ===================================================================
# ENDPOINT 1: LISTAR LOGS COM FILTROS E PAGINAÇÃO
# ===================================================================

@router.get("", response_model=AuditLogListResponse)
def get_audit_logs(
        store: GetStoreDep,
        db: GetDBDep,
        current_user: GetCurrentUserDep,
        # Filtros
        entity_type: Optional[AuditEntityType] = Query(None, description="Filtrar por tipo de entidade"),
        entity_id: Optional[int] = Query(None, description="Filtrar por ID da entidade"),
        action: Optional[AuditAction] = Query(None, description="Filtrar por tipo de ação"),
        user_id: Optional[int] = Query(None, description="Filtrar por usuário"),
        search: Optional[str] = Query(None, min_length=3, description="Buscar na descrição"),
        # Intervalo de datas
        start_date: Optional[datetime] = Query(None, description="Data inicial (ISO 8601)"),
        end_date: Optional[datetime] = Query(None, description="Data final (ISO 8601)"),
        days: int = Query(30, ge=1, le=365, description="Últimos N dias (se não informar datas)"),
        # Paginação
        page: int = Query(1, ge=1),
        size: int = Query(50, ge=1, le=500),
        # Ordenação
        order_by: Literal["created_at", "action", "entity_type"] = Query("created_at"),
        order: Literal["asc", "desc"] = Query("desc"),
):
    """
    Lista os logs de auditoria da loja com filtros avançados.

    **Casos de uso:**
    - Ver todas as ações de um usuário específico
    - Acompanhar mudanças em um produto específico
    - Auditar alterações de preços
    - Investigar ações suspeitas
    """

    # Monta a query base com relacionamentos
    query = db.query(models.AuditLog).options(
        joinedload(models.AuditLog.user),
        joinedload(models.AuditLog.store)
    ).filter(
        models.AuditLog.store_id == store.id
    )

    # Aplica filtro de data
    if start_date and end_date:
        query = query.filter(
            models.AuditLog.created_at >= start_date,
            models.AuditLog.created_at <= end_date
        )
    else:
        cutoff_date = datetime.now(timezone.utc) - timedelta(days=days)
        query = query.filter(models.AuditLog.created_at >= cutoff_date)

    # Aplica outros filtros
    if entity_type:
        query = query.filter(models.AuditLog.entity_type == entity_type.value)
    if entity_id:
        query = query.filter(models.AuditLog.entity_id == entity_id)
    if action:
        query = query.filter(models.AuditLog.action == action.value)
    if user_id:
        query = query.filter(models.AuditLog.user_id == user_id)
    if search:
        query = query.filter(models.AuditLog.description.ilike(f"%{search}%"))

    # Conta o total antes de paginar
    total = query.count()

    # Aplica ordenação
    if order == "desc":
        query = query.order_by(desc(getattr(models.AuditLog, order_by)))
    else:
        query = query.order_by(getattr(models.AuditLog, order_by))

    # Aplica paginação
    logs = query.offset((page - 1) * size).limit(size).all()

    return {
        "items": logs,
        "total": total,
        "page": page,
        "size": size,
        "pages": math.ceil(total / size)
    }


# ===================================================================
# ENDPOINT 2: DETALHES DE UM LOG ESPECÍFICO
# ===================================================================

@router.get("/{log_id}", response_model=AuditLogDetailResponse)
def get_audit_log_detail(
        store: GetStoreDep,
        db: GetDBDep,
        log_id: int = Path(..., description="ID do log de auditoria")
):
    """
    Retorna os detalhes completos de um log de auditoria,
    incluindo mudanças relacionadas na mesma entidade.
    """

    # Busca o log principal
    log = db.query(models.AuditLog).options(
        joinedload(models.AuditLog.user),
        joinedload(models.AuditLog.store)
    ).filter(
        models.AuditLog.id == log_id,
        models.AuditLog.store_id == store.id
    ).first()

    if not log:
        raise HTTPException(status_code=404, detail="Log de auditoria não encontrado")

    # Busca outras mudanças relacionadas (mesma entidade, últimos 30 dias)
    related_changes = []
    if log.entity_id:
        cutoff = datetime.now(timezone.utc) - timedelta(days=30)
        related_changes = db.query(models.AuditLog).filter(
            models.AuditLog.store_id == store.id,
            models.AuditLog.entity_type == log.entity_type,
            models.AuditLog.entity_id == log.entity_id,
            models.AuditLog.id != log_id,
            models.AuditLog.created_at >= cutoff
        ).order_by(desc(models.AuditLog.created_at)).limit(10).all()

    return {
        **log.__dict__,
        "related_changes": related_changes
    }


# ===================================================================
# ENDPOINT 3: HISTÓRICO COMPLETO DE UMA ENTIDADE
# ===================================================================

@router.get("/entity/{entity_type}/{entity_id}", response_model=EntityChangeHistory)
def get_entity_change_history(
        store: GetStoreDep,
        db: GetDBDep,
        entity_type: AuditEntityType = Path(..., description="Tipo da entidade"),
        entity_id: int = Path(..., description="ID da entidade"),
        limit: int = Query(100, ge=1, le=500, description="Máximo de registros")
):
    """
    Retorna todo o histórico de mudanças de uma entidade específica.

    **Exemplo:** Ver todas as alterações de preço de um produto.
    """

    changes = db.query(models.AuditLog).options(
        joinedload(models.AuditLog.user)
    ).filter(
        models.AuditLog.store_id == store.id,
        models.AuditLog.entity_type == entity_type.value,
        models.AuditLog.entity_id == entity_id
    ).order_by(desc(models.AuditLog.created_at)).limit(limit).all()

    total = db.query(func.count(models.AuditLog.id)).filter(
        models.AuditLog.store_id == store.id,
        models.AuditLog.entity_type == entity_type.value,
        models.AuditLog.entity_id == entity_id
    ).scalar()

    return {
        "entity_type": entity_type,
        "entity_id": entity_id,
        "changes": changes,
        "total_changes": total
    }


# ===================================================================
# ENDPOINT 4: ESTATÍSTICAS DE AUDITORIA
# ===================================================================

@router.get("/stats/overview", response_model=AuditStatistics)
def get_audit_statistics(
        store: GetStoreDep,
        db: GetDBDep,
        days: int = Query(30, ge=1, le=365, description="Período para análise")
):
    """
    Retorna estatísticas agregadas sobre as ações de auditoria.

    **Útil para:**
    - Dashboard administrativo
    - Relatórios de atividade
    - Identificar padrões de uso
    """

    cutoff_date = datetime.now(timezone.utc) - timedelta(days=days)

    # Total de logs no período
    total_logs = db.query(func.count(models.AuditLog.id)).filter(
        models.AuditLog.store_id == store.id,
        models.AuditLog.created_at >= cutoff_date
    ).scalar()

    # Top 5 ações mais comuns
    top_actions = db.query(
        models.AuditLog.action,
        func.count(models.AuditLog.id).label('count'),
        func.max(models.AuditLog.created_at).label('last_occurrence')
    ).filter(
        models.AuditLog.store_id == store.id,
        models.AuditLog.created_at >= cutoff_date
    ).group_by(
        models.AuditLog.action
    ).order_by(
        desc('count')
    ).limit(5).all()

    # Usuário mais ativo
    most_active = db.query(
        models.User.id,
        models.User.name,
        func.count(models.AuditLog.id).label('total_actions'),
        func.max(models.AuditLog.created_at).label('last_action_at')
    ).join(
        models.AuditLog, models.AuditLog.user_id == models.User.id
    ).filter(
        models.AuditLog.store_id == store.id,
        models.AuditLog.created_at >= cutoff_date
    ).group_by(
        models.User.id, models.User.name
    ).order_by(
        desc('total_actions')
    ).first()

    # Ação mais comum do usuário mais ativo
    most_common_action = None
    if most_active:
        most_common_action = db.query(
            models.AuditLog.action
        ).filter(
            models.AuditLog.store_id == store.id,
            models.AuditLog.user_id == most_active.id,
            models.AuditLog.created_at >= cutoff_date
        ).group_by(
            models.AuditLog.action
        ).order_by(
            desc(func.count(models.AuditLog.id))
        ).first()

    # Atividade diária (últimos 7 dias)
    daily_activity = db.query(
        func.date(models.AuditLog.created_at).label('date'),
        func.count(models.AuditLog.id).label('total_actions'),
        func.count(func.distinct(models.AuditLog.user_id)).label('unique_users')
    ).filter(
        models.AuditLog.store_id == store.id,
        models.AuditLog.created_at >= datetime.now(timezone.utc) - timedelta(days=7)
    ).group_by(
        func.date(models.AuditLog.created_at)
    ).order_by(
        'date'
    ).all()

    return {
        "total_logs": total_logs,
        "date_range_days": days,
        "most_active_user": {
            "user_id": most_active.id,
            "user_name": most_active.name,
            "total_actions": most_active.total_actions,
            "most_common_action": most_common_action[0] if most_common_action else "N/A",
            "last_action_at": most_active.last_action_at
        } if most_active else None,
        "top_actions": [
            {
                "action": action,
                "count": count,
                "last_occurrence": last_occurrence
            }
            for action, count, last_occurrence in top_actions
        ],
        "daily_activity": [
            {
                "date": date.isoformat(),
                "total_actions": total_actions,
                "unique_users": unique_users,
                "most_common_action": "N/A"  # Pode adicionar lógica depois
            }
            for date, total_actions, unique_users in daily_activity
        ]
    }


# ===================================================================
# ENDPOINT 5: AÇÕES DE UM USUÁRIO ESPECÍFICO
# ===================================================================

@router.get("/user/{user_id}", response_model=AuditLogListResponse)
def get_user_audit_logs(
        store: GetStoreDep,
        db: GetDBDep,
        user_id: int = Path(..., description="ID do usuário"),
        days: int = Query(30, ge=1, le=365),
        page: int = Query(1, ge=1),
        size: int = Query(50, ge=1, le=200),
):
    """
    Lista todas as ações de um usuário específico.

    **Útil para:**
    - Auditoria de funcionários
    - Rastreamento de atividades
    """

    cutoff_date = datetime.now(timezone.utc) - timedelta(days=days)

    query = db.query(models.AuditLog).options(
        joinedload(models.AuditLog.user)
    ).filter(
        models.AuditLog.store_id == store.id,
        models.AuditLog.user_id == user_id,
        models.AuditLog.created_at >= cutoff_date
    )

    total = query.count()
    logs = query.order_by(
        desc(models.AuditLog.created_at)
    ).offset((page - 1) * size).limit(size).all()

    return {
        "items": logs,
        "total": total,
        "page": page,
        "size": size,
        "pages": math.ceil(total / size)
    }