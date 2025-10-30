# Em: src/api/admin/routes/dashboard.py

from fastapi import APIRouter, Query
from datetime import date, timedelta

from src.api.admin.services.dashboard_service import get_dashboard_data_for_period
from src.api.schemas.analytics.dashboard import (
    DashboardDataSchema,

)
from src.core.database import GetDBDep

router = APIRouter(
    prefix="/admin/stores/{store_id}/dashboard",  # Endpoint um pouco mais limpo
    tags=["Admin - Dashboard"],
)
@router.get("/", response_model=DashboardDataSchema)
def get_dashboard_summary(
        db: GetDBDep,
        store_id: int,
        start_date: date = date.today() - timedelta(days=29),
        end_date: date = date.today(),
        order_type: str | None = Query(None, description="Filtrar por tipo: delivery, pickup, table")
):
    """
    Retorna um resumo de dados agregados para o dashboard da loja.
    Agora apenas chama o serviço central para fazer o trabalho pesado.
    """
    # ✅ A rota agora é apenas uma linha que chama o serviço!
    return get_dashboard_data_for_period(db, store_id, start_date, end_date, order_type=order_type)