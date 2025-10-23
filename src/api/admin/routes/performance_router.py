# src/api/admin/routes/performance_router.py

import math
from typing import Optional
from datetime import date, datetime, time

from fastapi import APIRouter, Query, HTTPException
from sqlalchemy import cast, String, func, or_, exists, select, and_
from sqlalchemy.orm import aliased

from src.api.admin.utils.input_sanitizer import sanitize_search_input
from src.api.schemas.orders.order import OrderDetails
from src.api.schemas.shared.pagination import PaginatedResponse
from src.core import models
from src.core.database import GetDBDep
from src.core.dependencies import GetStoreDep
from src.api.schemas.analytics.performance import StorePerformanceSchema, TodaySummarySchema
from src.api.admin.services.performance_service import get_store_performance_for_date, get_today_summary
from src.core.utils.enums import SalesChannel

router = APIRouter(
    prefix="/stores/{store_id}/performance",
    tags=["Performance Analytics"]
)


@router.get("", response_model=StorePerformanceSchema)
def get_performance_data(
        db: GetDBDep,
        store: GetStoreDep,
        start_date: date = Query(..., description="Data de início do período no formato YYYY-MM-DD"),
        end_date: date = Query(..., description="Data de fim do período no formato YYYY-MM-DD"),
):
    """Resumo de desempenho da loja em uma data específica"""
    try:
        performance_data = get_store_performance_for_date(db, store.id, start_date, end_date)
        return performance_data
    except Exception as e:
        print(f"❌ Erro ao calcular desempenho para loja {store.id}: {e}")
        raise HTTPException(status_code=500, detail="Erro ao processar os dados de desempenho.")


@router.get("/list-by-date", response_model=PaginatedResponse[OrderDetails])
def list_orders_by_date(
        db: GetDBDep,
        store: GetStoreDep,
        start_date: date = Query(..., description="Data de início do período"),
        end_date: date = Query(..., description="Data de fim do período"),
        search: Optional[str] = Query(None, description="Busca por nome, ID do pedido ou mesa"),
        order_type: Optional[str] = Query(None, description="Filtra por tipo: delivery, table, pickup"),  # ✅ NOVO
        status: Optional[str] = Query(None, description="Filtra por status do pedido"),
        sort_by: str = Query("created_at", description="Campo para ordenação"),
        sort_order: str = Query("desc", description="Ordem 'asc' ou 'desc'"),
        page: int = Query(1, ge=1),
        size: int = Query(10, ge=1, le=100),
):
    """
    ✅ VERSÃO CORRIGIDA: Lista pedidos de TODOS os tipos (delivery, mesa, pickup)
    """
    start_of_period = datetime.combine(start_date, time.min)
    end_of_period = datetime.combine(end_date, time.max)

    # Base query
    query = db.query(models.Order).filter(
        models.Order.store_id == store.id,
        models.Order.created_at.between(start_of_period, end_of_period)
    )

    # ✅ FILTRO POR TIPO DE PEDIDO
    if order_type:
        valid_types = [SalesChannel.MENU, SalesChannel.TABLE]
        if order_type not in valid_types:
            raise HTTPException(
                status_code=400,
                detail=f"Tipo de pedido inválido. Valores permitidos: {valid_types}"
            )
        query = query.filter(models.Order.order_type == order_type)

    # ✅ BUSCA SEGURA - TRATA CUSTOMER_NAME NULL
    if search:
        # Sanitiza input contra SQL Injection
        search_clean = sanitize_search_input(search)
        search_pattern = f"%{search_clean}%"

        # Cria subquery para buscar nome da mesa
        table_subquery = exists(
            select(1).where(
                and_(
                    models.Tables.id == models.Order.table_id,
                    models.Tables.name.ilike(search_pattern)
                )
            )
        )

        query = query.filter(
            or_(
                # ✅ Usa coalesce para tratar NULL
                func.coalesce(models.Order.customer_name, '').ilike(search_pattern),
                # Busca por ID público
                cast(models.Order.public_id, String).ilike(search_pattern),
                # ✅ Busca por nome da mesa
                table_subquery
            )
        )

    # ✅ FILTRO POR STATUS (com whitelist)
    if status:
        valid_statuses = [
            'pending', 'confirmed', 'preparing', 'ready',
            'in_delivery', 'delivered', 'cancelled'
        ]
        if status not in valid_statuses:
            raise HTTPException(
                status_code=400,
                detail=f"Status inválido. Valores permitidos: {valid_statuses}"
            )
        query = query.filter(models.Order.order_status == status)

    # Total de itens
    total_items = query.count()

    # ✅ ORDENAÇÃO SEGURA (whitelist)
    valid_sort_fields = ['created_at', 'public_id', 'customer_name', 'total_price', 'order_type']
    if sort_by not in valid_sort_fields:
        raise HTTPException(
            status_code=400,
            detail=f"Campo de ordenação inválido. Valores permitidos: {valid_sort_fields}"
        )

    order_column = getattr(models.Order, sort_by, models.Order.created_at)

    if sort_order not in ['asc', 'desc']:
        raise HTTPException(
            status_code=400,
            detail="Ordem inválida. Valores permitidos: 'asc' ou 'desc'"
        )

    query = query.order_by(
        order_column.desc() if sort_order == "desc" else order_column.asc()
    )

    # Paginação
    items = query.offset((page - 1) * size).limit(size).all()

    return PaginatedResponse(
        items=items,
        total_items=total_items,
        total_pages=math.ceil(total_items / size),
        page=page,
        size=size,
    )


@router.get(
    "/today-summary",
    response_model=TodaySummarySchema,
    summary="Obtém um resumo rápido das vendas do dia de operação atual"
)
def get_today_summary_data(
        db: GetDBDep,
        store: GetStoreDep,
):
    return get_today_summary(db, store.id)