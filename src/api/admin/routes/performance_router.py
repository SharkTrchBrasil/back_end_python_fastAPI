# src/api/admin/routers/performance_router.py
import math
from typing import Optional

from fastapi import APIRouter, Depends, Query, HTTPException  # Remova HTTPException se não for usado diretamente aqui
from sqlalchemy import cast, String
from sqlalchemy.orm import Session
from datetime import date, datetime, time

from src.api.schemas.order import OrderDetails
from src.api.schemas.pagination import PaginatedResponse
from src.core import models
from src.core.database import GetDBDep
from src.core.dependencies import GetStoreDep
from src.api.schemas.performance import StorePerformanceSchema
from src.api.admin.services.performance_service import get_store_performance_for_date


router = APIRouter(prefix="/stores/{store_id}/performance", tags=["Performance Analytics"])


@router.get(
    "/", # ✅ MUDANÇA 2: O caminho agora é a raiz do prefixo.
    response_model=StorePerformanceSchema,
    summary="Obtém dados de desempenho para uma loja em uma data específica"
)
def get_performance_data(
    # ✅ MUDANÇA 3: Remova 'store_id: int', pois a dependência 'GetStoreDep' já cuida disso.
    db: GetDBDep,
    store: GetStoreDep,
    target_date: date = Query(..., description="A data para a análise no formato YYYY-MM-DD."),
):
    """
    Endpoint para a página de desempenho do Flutter.
    ...
    """
    try:
        # O 'store' já vem validado e carregado pela dependência GetStoreDep.
        performance_data = get_store_performance_for_date(db, store.id, target_date)
        return performance_data
    except Exception as e:
        print(f"❌ Erro ao calcular desempenho para loja {store.id}: {e}")
        # Retornar um erro 500 genérico é mais seguro em produção.
        # A exceção específica pode ser logada no seu servidor.
        raise HTTPException(status_code=500, detail="Ocorreu um erro ao processar os dados de desempenho.")


@router.get(
    "/list-by-date",  # Um nome de rota claro
    response_model=PaginatedResponse[OrderDetails],
    summary="Lista pedidos de uma data com filtros, ordenação e paginação"
)


def list_orders_by_date(

        db: GetDBDep,
        store: GetStoreDep,
        target_date: date = Query(..., description="A data para a análise"),
        search: Optional[str] = Query(None, description="Busca por nome do cliente ou ID do pedido"),
        status: Optional[str] = Query(None, description="Filtra por status do pedido (ex: delivered, canceled)"),
        sort_by: str = Query("created_at", description="Campo para ordenação"),
        sort_order: str = Query("desc", description="Ordem ('asc' ou 'desc')"),
        page: int = Query(1, ge=1, description="Número da página"),
        size: int = Query(10, ge=1, le=100, description="Itens por página"),
):
    start_of_day = datetime.combine(target_date, time.min)
    end_of_day = datetime.combine(target_date, time.max)

    # Query base
    query = db.query(models.Order).filter(
        models.Order.store_id == store.id,
        models.Order.created_at.between(start_of_day, end_of_day)
    )

    # Filtro de busca
    if search:
        search_term = f"%{search}%"
        query = query.filter(
            (models.Order.customer_name.ilike(search_term)) |
            (cast(models.Order.public_id, String).ilike(search_term))
        )

    # Filtro de status
    if status:
        query = query.filter(models.Order.order_status == status)

    # Contagem total de itens (antes da paginação)
    total_items = query.count()

    # Ordenação
    order_column = getattr(models.Order, sort_by, models.Order.created_at)
    if sort_order == "desc":
        query = query.order_by(order_column.desc())
    else:
        query = query.order_by(order_column.asc())

    # Paginação
    items = query.offset((page - 1) * size).limit(size).all()

    return PaginatedResponse(
        items=items,
        total_items=total_items,
        total_pages=math.ceil(total_items / size),
        page=page,
        size=size
    )