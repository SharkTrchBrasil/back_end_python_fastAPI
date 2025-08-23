# src/api/admin/services/performance_service.py
from sqlalchemy.orm import Session
from sqlalchemy import func, case, and_
from datetime import date, datetime, time, timedelta

from src.core import models
from src.core.utils.enums import OrderStatus
from src.api.schemas.performance import (
    StorePerformanceSchema,
    DailySummarySchema,
    ComparativeMetricSchema,
    CustomerAnalyticsSchema,
    SalesByHourSchema,
    PaymentMethodSummarySchema,
    TopSellingProductSchema,
    OrderStatusCountSchema,
)


def _build_comparative_metric(current, previous) -> ComparativeMetricSchema:
    """Helper para criar a métrica comparativa e calcular a porcentagem."""
    current = float(current or 0.0)
    previous = float(previous or 0.0)

    change = 0.0
    if previous > 0:
        change = ((current - previous) / previous) * 100

    return ComparativeMetricSchema(current=current, previous=previous, change_percentage=change)


def get_store_performance_for_date(db: Session, store_id: int, target_date: date) -> StorePerformanceSchema:
    # --- 1. Definir Períodos de Tempo ---
    comparison_date = target_date - timedelta(days=7)
    start_current, end_current = datetime.combine(target_date, time.min), datetime.combine(target_date, time.max)
    start_previous, end_previous = datetime.combine(comparison_date, time.min), datetime.combine(comparison_date,
                                                                                                 time.max)

    # --- 2. Query de Vendas e Lucro (Apenas para pedidos concluídos) ---
    COMPLETED_STATUS = OrderStatus.DELIVERED.value
    sales_profit_results = db.query(
        func.sum(case((models.Order.created_at.between(start_current, end_current), models.Order.total_price),
                      else_=0)).label("current_total_value"),
        func.count(
            case((models.Order.created_at.between(start_current, end_current), models.Order.id), else_=None)).label(
            "current_sales_count"),
        func.sum(case((models.Order.created_at.between(start_current, end_current),
                       (models.OrderProduct.price - models.Product.cost_price) * models.OrderProduct.quantity),
                      else_=0)).label("current_gross_profit"),
        func.sum(case((models.Order.created_at.between(start_previous, end_previous), models.Order.total_price),
                      else_=0)).label("previous_total_value"),
        func.count(
            case((models.Order.created_at.between(start_previous, end_previous), models.Order.id), else_=None)).label(
            "previous_sales_count"),
        func.sum(case((models.Order.created_at.between(start_previous, end_previous),
                       (models.OrderProduct.price - models.Product.cost_price) * models.OrderProduct.quantity),
                      else_=0)).label("previous_gross_profit")
    ).join(models.OrderProduct, models.Order.id == models.OrderProduct.order_id).join(models.Product,
                                                                                      models.OrderProduct.product_id == models.Product.id).filter(
        models.Order.store_id == store_id,
        models.Order.order_status == COMPLETED_STATUS,
        (models.Order.created_at.between(start_current, end_current)) | (
            models.Order.created_at.between(start_previous, end_previous))
    ).one_or_none()

    # --- 3. Processar Resultados de Vendas e Lucro ---
    current_total_value = (sales_profit_results.current_total_value or 0) / 100
    previous_total_value = (sales_profit_results.previous_total_value or 0) / 100
    current_sales_count = sales_profit_results.current_sales_count or 0
    previous_sales_count = sales_profit_results.previous_sales_count or 0
    current_gross_profit = (sales_profit_results.current_gross_profit or 0) / 100
    previous_gross_profit = (sales_profit_results.previous_gross_profit or 0) / 100

    summary = DailySummarySchema(
        completed_sales=_build_comparative_metric(current_sales_count, previous_sales_count),
        total_value=_build_comparative_metric(current_total_value, previous_total_value),
        average_ticket=_build_comparative_metric(
            current_total_value / current_sales_count if current_sales_count else 0,
            previous_total_value / previous_sales_count if previous_sales_count else 0)
    )
    gross_profit = _build_comparative_metric(current_gross_profit, previous_gross_profit)

    # --- 4. Análise de Clientes ---
    def get_customer_analytics(day):
        customer_ids_on_day = {row.customer_id for row in
                               db.query(models.Order.customer_id).filter(models.Order.store_id == store_id,
                                                                         func.date(models.Order.created_at) == day,
                                                                         models.Order.customer_id.isnot(
                                                                             None)).distinct()}
        if not customer_ids_on_day: return 0, 0
        new_customers_count = db.query(func.count(models.StoreCustomer.customer_id)).filter(
            models.StoreCustomer.store_id == store_id, models.StoreCustomer.customer_id.in_(customer_ids_on_day),
            func.date(models.StoreCustomer.created_at) == day).scalar() or 0
        return new_customers_count, len(customer_ids_on_day) - new_customers_count

    current_new, current_returning = get_customer_analytics(target_date)
    previous_new, previous_returning = get_customer_analytics(comparison_date)
    customer_analytics = CustomerAnalyticsSchema(new_customers=_build_comparative_metric(current_new, previous_new),
                                                 returning_customers=_build_comparative_metric(current_returning,
                                                                                               previous_returning))

    # --- 5. Dados para Gráficos (Apenas do dia atual) ---
    base_current_day_query = db.query(models.Order).filter(models.Order.store_id == store_id,
                                                           models.Order.created_at.between(start_current, end_current))

    sales_by_hour_data = base_current_day_query.filter(models.Order.order_status == COMPLETED_STATUS).with_entities(
        func.extract('hour', models.Order.created_at).label("hour"),
        func.sum(models.Order.total_price).label("total_value")).group_by("hour").order_by("hour").all()
    sales_by_hour = [SalesByHourSchema(hour=r.hour, totalValue=(r.total_value or 0) / 100) for r in sales_by_hour_data]

    payment_methods_data = base_current_day_query.filter(models.Order.order_status == COMPLETED_STATUS).join(
        models.Order.payment_method).join(models.StorePaymentMethodActivation.platform_method).with_entities(
        models.PlatformPaymentMethod.name, models.PlatformPaymentMethod.icon_key,
        func.sum(models.Order.total_price).label("total_value"), func.count(models.Order.id).label("count")).group_by(
        models.PlatformPaymentMethod.name, models.PlatformPaymentMethod.icon_key).all()
    payment_methods = [
        PaymentMethodSummarySchema(method_name=r.name, method_icon=r.icon_key, total_value=(r.total_value or 0) / 100,
                                   transaction_count=r.count) for r in payment_methods_data]

    top_selling_products_data = db.query(models.Product.id, models.Product.name,
                                         func.sum(models.OrderProduct.quantity).label("qty"),
                                         func.sum(models.OrderProduct.price * models.OrderProduct.quantity).label(
                                             "value")).join(models.OrderProduct,
                                                            models.Product.id == models.OrderProduct.product_id).join(
        models.Order, models.OrderProduct.order_id == models.Order.id).filter(models.Order.store_id == store_id,
                                                                              models.Order.created_at.between(
                                                                                  start_current, end_current),
                                                                              models.Order.order_status == COMPLETED_STATUS).group_by(
        models.Product.id, models.Product.name).order_by(func.sum(models.OrderProduct.quantity).desc()).limit(5).all()
    top_selling_products = [TopSellingProductSchema(product_id=p.id, product_name=p.name, quantity_sold=p.qty,
                                                    total_value=(p.value or 0) / 100) for p in
                            top_selling_products_data]

    status_counts_data = {row.order_status: row.count for row in
                          base_current_day_query.with_entities(models.Order.order_status,
                                                               func.count(models.Order.id).label("count")).group_by(
                              models.Order.order_status).all()}
    order_status_counts = OrderStatusCountSchema(concluidos=status_counts_data.get(OrderStatus.DELIVERED.value, 0),
                                                 cancelados=status_counts_data.get(OrderStatus.CANCELED.value, 0),
                                                 pendentes=status_counts_data.get(OrderStatus.PENDING.value, 0))

    # --- 6. Montar a Resposta Final ---
    return StorePerformanceSchema(
        query_date=target_date,
        comparison_date=comparison_date,
        summary=summary,
        gross_profit=gross_profit,
        customer_analytics=customer_analytics,
        sales_by_hour=sales_by_hour,
        payment_methods=payment_methods,
        top_selling_products=top_selling_products,
        order_status_counts=order_status_counts,
    )