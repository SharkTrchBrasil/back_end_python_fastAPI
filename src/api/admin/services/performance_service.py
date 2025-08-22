# src/api/admin/services/performance_service.py

from sqlalchemy.orm import Session
from sqlalchemy import func, case, and_
from datetime import date, datetime, time, timezone

from src.core import models
from src.api.schemas.performance import (
    StorePerformanceSchema,
    DailySummarySchema,
    SalesByHourSchema,
    PaymentMethodSummarySchema,
    TopSellingProductSchema,
    CustomerAnalyticsSchema
)
from src.core.utils.enums import OrderStatus


def get_store_performance_for_date(db: Session, store_id: int, target_date: date) -> StorePerformanceSchema:
    """
    Calcula e retorna todas as métricas de desempenho para uma loja em uma data específica.
    """
    start_of_day = datetime.combine(target_date, time.min, tzinfo=timezone.utc)
    end_of_day = datetime.combine(target_date, time.max, tzinfo=timezone.utc)

    # Status que consideramos como "pedido concluído" para as métricas.
    # Ajuste conforme sua regra de negócio (ex: 'delivered', 'completed').
    COMPLETED_STATUS = OrderStatus.DELIVERED.value

    # --- 1. Consulta Base para Pedidos Concluídos ---
    base_query = db.query(models.Order).filter(
        models.Order.store_id == store_id,
        models.Order.created_at.between(start_of_day, end_of_day),
        models.Order.order_status == COMPLETED_STATUS
    )

    # --- 2. KPIs Principais (DailySummary) ---
    summary_metrics = base_query.with_entities(
        func.count(models.Order.id).label("completed_sales"),
        func.sum(models.Order.total_price).label("total_value")
    ).one()

    completed_sales = summary_metrics.completed_sales or 0
    # Dividimos por 100 pois os preços estão em centavos.
    total_value = (summary_metrics.total_value or 0) / 100
    average_ticket = (total_value / completed_sales) if completed_sales > 0 else 0

    summary = DailySummarySchema(
        completed_sales=completed_sales,
        total_value=total_value,
        average_ticket=average_ticket
    )

    # --- 3. Vendas por Hora ---
    sales_by_hour_data = base_query.with_entities(
        func.extract('hour', models.Order.created_at).label("hour"),
        func.sum(models.Order.total_price).label("total_value")
    ).group_by("hour").order_by("hour").all()

    sales_by_hour = [
        SalesByHourSchema(hour=row.hour, totalValue=row.total_value / 100 if row.total_value else 0)
        for row in sales_by_hour_data
    ]

    # --- 4. Formas de Pagamento ---
    payment_methods_data = base_query.join(
        models.Order.payment_method
    ).join(
        models.StorePaymentMethodActivation.platform_method
    ).with_entities(
        models.PlatformPaymentMethod.name.label("method_name"),
        func.sum(models.Order.total_price).label("total_value"),
        func.count(models.Order.id).label("transaction_count")
    ).group_by("method_name").all()

    payment_methods = [
        PaymentMethodSummarySchema(
            method_name=row.method_name,
            total_value=row.total_value / 100 if row.total_value else 0,
            transaction_count=row.transaction_count
        ) for row in payment_methods_data
    ]

    # --- 5. Produtos Mais Vendidos ---
    top_selling_products_data = db.query(
        models.Product.id.label("product_id"),
        models.Product.name.label("product_name"),
        func.sum(models.OrderProduct.quantity).label("quantity_sold"),
        func.sum(models.OrderProduct.price * models.OrderProduct.quantity).label("total_value")
    ).join(
        models.OrderProduct, models.Product.id == models.OrderProduct.product_id
    ).join(
        models.Order, models.OrderProduct.order_id == models.Order.id
    ).filter(
        models.Order.store_id == store_id,
        models.Order.created_at.between(start_of_day, end_of_day),
        models.Order.order_status == COMPLETED_STATUS
    ).group_by(models.Product.id, models.Product.name).order_by(
        func.sum(models.OrderProduct.quantity).desc()
    ).limit(5).all()

    top_selling_products = [
        TopSellingProductSchema(
            product_id=p.product_id,
            product_name=p.product_name,
            quantity_sold=p.quantity_sold,
            total_value=p.total_value / 100 if p.total_value else 0
        ) for p in top_selling_products_data
    ]

    # --- 6. Clientes Novos vs. Recorrentes ---
    customers_on_date = base_query.with_entities(
        models.Order.customer_id
    ).distinct().all()

    customer_ids = [c.customer_id for c in customers_on_date if c.customer_id is not None]

    new_customers_count = 0
    if customer_ids:
        # Conta quantos dos clientes do dia foram criados NAQUELE dia na tabela de relacionamento.
        new_customers_count = db.query(func.count(models.StoreCustomer.customer_id)).filter(
            models.StoreCustomer.store_id == store_id,
            models.StoreCustomer.customer_id.in_(customer_ids),
            func.date(models.StoreCustomer.created_at) == target_date
        ).scalar() or 0

    customer_analytics = CustomerAnalyticsSchema(
        new_customers=new_customers_count,
        returning_customers=len(customer_ids) - new_customers_count
    )

    # --- 7. Monta o Objeto Final ---
    return StorePerformanceSchema(
        query_date=target_date,
        summary=summary,
        sales_by_hour=sales_by_hour,
        payment_methods=payment_methods,
        top_selling_products=top_selling_products,
        customer_analytics=customer_analytics
    )