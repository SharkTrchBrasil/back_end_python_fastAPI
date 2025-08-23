# src/api/admin/routers/performance_router.py
import math
from typing import Optional
from datetime import date, datetime, time

from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy import cast, String
from sqlalchemy.orm import Session

from src.api.schemas.order import OrderDetails
from src.api.schemas.pagination import PaginatedResponse
from src.core import models
from src.core.database import GetDBDep
from src.core.dependencies import GetStoreDep
from src.api.schemas.performance import StorePerformanceSchema
from src.api.admin.services.performance_service import get_store_performance_for_date

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
        # ✅ ALTERADO: Passamos o período para o serviço
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
    search: Optional[str] = Query(None, description="Busca por nome ou ID do pedido"),
    status: Optional[str] = Query(None, description="Filtra por status do pedido"),
    sort_by: str = Query("created_at", description="Campo para ordenação"),
    sort_order: str = Query("desc", description="Ordem 'asc' ou 'desc'"),
    page: int = Query(1, ge=1),
    size: int = Query(10, ge=1, le=100),
):

    start_of_period = datetime.combine(start_date, time.min)
    end_of_period = datetime.combine(end_date, time.max)

    # A query agora usa o período correto
    query = db.query(models.Order).filter(
        models.Order.store_id == store.id,
        models.Order.created_at.between(start_of_period, end_of_period)
    )

    if search:
        search_term = f"%{search}%"
        query = query.filter(
            (models.Order.customer_name.ilike(search_term)) |
            (cast(models.Order.public_id, String).ilike(search_term))
        )

    if status:
        query = query.filter(models.Order.order_status == status)

    total_items = query.count()

    order_column = getattr(models.Order, sort_by, models.Order.created_at)
    query = query.order_by(order_column.desc() if sort_order == "desc" else order_column.asc())

    items = query.offset((page - 1) * size).limit(size).all()

    return PaginatedResponse(
        items=items,
        total_items=total_items,
        total_pages=math.ceil(total_items / size),
        page=page,
        size=size,
    )
