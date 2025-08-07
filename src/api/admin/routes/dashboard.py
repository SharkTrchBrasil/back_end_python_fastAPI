# Em: src/api/admin/routes/dashboard.py (ou onde preferir)

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func, distinct
from datetime import date, timedelta

# Importe seus modelos do SQLAlchemy e o schema de resposta
from src.core import models
from src.api.admin.schemas.dashboard import (
    DashboardDataSchema,
    DashboardKpiSchema,
    SalesDataPointSchema,
    TopItemSchema,
)
# Importe sua função para obter a sessão do DB e o usuário autenticado
from src.core.database import get_db

# from src.api.admin.dependencies import get_current_admin_user

router = APIRouter(
    prefix="/admin/stores/{store_id}/dashboard-summary",
    tags=["Admin - Dashboard"],
)



@router.get("/", response_model=DashboardDataSchema)
def get_dashboard_summary(
        store_id: int,
        # Opcional: adicione filtros de data como query parameters
        start_date: date = date.today() - timedelta(days=7),
        end_date: date = date.today(),
        db: Session = Depends(get_db),
        # current_user: models.User = Depends(get_current_admin_user), # Proteja sua rota
):
    """
    Retorna um resumo de dados agregados para o dashboard da loja.
    """

    # --- 1. Cálculo dos KPIs ---

    kpi_query = db.query(
        func.sum(models.Order.discounted_total_price).label("total_revenue"),
        func.count(models.Order.id).label("total_orders"),
        func.count(distinct(models.Order.customer_id)).label("total_customers")  # Exemplo, ajuste se necessário
    ).filter(
        models.Order.store_id == store_id,
        models.Order.created_at.between(start_date, end_date),
        models.Order.order_status == 'completed'  # Garante que só pedidos finalizados contam
    ).first()

    total_revenue = kpi_query.total_revenue or 0.0
    total_orders = kpi_query.total_orders or 0
    average_ticket = (total_revenue / total_orders) if total_orders > 0 else 0.0

    # O cálculo de "novos clientes" é mais complexo e pode exigir uma subquery,
    # mas aqui está um exemplo simplificado.
    new_customers = 0  # Placeholder

    kpis = DashboardKpiSchema(
        total_revenue=total_revenue / 100,  # Dividir por 100 se o preço estiver em centavos
        total_orders=total_orders,
        average_ticket=average_ticket / 100,
        new_customers=new_customers
    )

    # --- 2. Dados para o Gráfico de Vendas (por dia) ---

    sales_over_time_query = db.query(
        func.date(models.Order.created_at).label("period"),
        func.sum(models.Order.discounted_total_price).label("revenue")
    ).filter(
        models.Order.store_id == store_id,
        models.Order.created_at.between(start_date, end_date),
        models.Order.order_status == 'completed'
    ).group_by(
        func.date(models.Order.created_at)
    ).order_by(
        func.date(models.Order.created_at)
    ).all()

    sales_over_time = [
        SalesDataPointSchema(period=str(row.period), revenue=row.revenue / 100 if row.revenue else 0.0)
        for row in sales_over_time_query
    ]

    # --- 3. Top 5 Produtos Mais Vendidos ---

    top_products_query = db.query(
        models.OrderProduct.name,
        func.sum(models.OrderProduct.quantity).label("count")
    ).join(models.Order).filter(
        models.Order.store_id == store_id,
        models.Order.created_at.between(start_date, end_date),
        models.Order.order_status == 'completed'
    ).group_by(
        models.OrderProduct.name
    ).order_by(
        func.sum(models.OrderProduct.quantity).desc()
    ).limit(5).all()

    top_products = [TopItemSchema(name=row.name, count=row.count) for row in top_products_query]

    # --- 4. Top 5 Categorias Mais Populares (exige join com produtos e categorias) ---

    # Esta query é mais complexa e depende da sua estrutura de models
    # Aqui está um placeholder
    top_categories = []

    # --- 5. Monta a Resposta Final ---

    return DashboardDataSchema(
        kpis=kpis,
        sales_over_time=sales_over_time,
        top_products=top_products,
        top_categories=top_categories,
    )