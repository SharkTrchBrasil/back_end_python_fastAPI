# src/api/admin/services/performance_service.py
from __future__ import annotations

from datetime import date, datetime, time, timedelta
from typing import Iterable, Optional, Tuple

from sqlalchemy import and_, case, func
from sqlalchemy.orm import Session

from src.core import models
from src.core.utils.enums import OrderStatus
from src.api.schemas.performance import (
    ComparativeMetricSchema,
    CouponPerformanceSchema,
    CustomerAnalyticsSchema,
    DailySummarySchema,
    OrderStatusCountSchema,
    PaymentMethodSummarySchema,
    SalesByHourSchema,
    StorePerformanceSchema,
    TopAddonSchema,
    TopSellingProductSchema, CategoryPerformanceSchema, ProductFunnelSchema, TodaySummarySchema, DailyTrendPointSchema,
)


# ------------- Utils / Helpers -------------

def _to_real(value: Optional[int | float]) -> float:
    """Converte centavos para reais (ou retorna 0.0)."""
    return float((value or 0) / 100)


def _build_comparative_metric(current, previous) -> ComparativeMetricSchema:
    """Cria métrica comparativa com % de variação (prev > 0)."""
    current = float(current or 0.0)
    previous = float(previous or 0.0)
    change = ((current - previous) / previous) * 100 if previous > 0 else 0.0
    return ComparativeMetricSchema(current=current, previous=previous, change_percentage=change)


def _time_range_for_day(target: date) -> Tuple[datetime, datetime]:
    """Retorna (start_of_day, end_of_day) para a data."""
    return datetime.combine(target, time.min), datetime.combine(target, time.max)


def _orders_base_query(
    db: Session,
    store_id: int,
    start_dt: datetime,
    end_dt: datetime,
    status: Optional[str] = None,
):
    """Query base de pedidos por loja e intervalo, com status opcional."""
    q = db.query(models.Order).filter(
        models.Order.store_id == store_id,
        models.Order.created_at.between(start_dt, end_dt),
    )
    if status:
        q = q.filter(models.Order.order_status == status)
    return q


# ------------- Blocos de cálculo -------------

def _calc_sales_and_profit(
    db: Session,
    store_id: int,
    start_current: datetime,
    end_current: datetime,
    start_previous: datetime,
    end_previous: datetime,
) -> Tuple[DailySummarySchema, ComparativeMetricSchema]:
    """
    Agregações de vendas e lucro bruto comparando dia atual vs. dia comparativo.
    Trata ausência de dados e custo nulo.
    """
    COMPLETED = OrderStatus.DELIVERED.value  # string esperada no banco

    # price e cost_price são em centavos
    # lucro bruto por item = (preco_venda - custo) * quantidade
    gross_expr_current = (
        func.coalesce(
            (models.OrderProduct.price - func.coalesce(models.Product.cost_price, 0)),
            0,
        ) * models.OrderProduct.quantity
    )

    gross_expr_previous = (
        func.coalesce(
            (models.OrderProduct.price - func.coalesce(models.Product.cost_price, 0)),
            0,
        ) * models.OrderProduct.quantity
    )

    agg = (
        db.query(
            # Totais do período atual
            func.sum(
                case(
                    (models.Order.created_at.between(start_current, end_current), models.Order.total_price),
                    else_=0,
                )
            ).label("current_total_value"),
            func.count(
                case(
                    (models.Order.created_at.between(start_current, end_current), models.Order.id),
                    else_=None,
                )
            ).label("current_sales_count"),
            func.sum(
                case(
                    (models.Order.created_at.between(start_current, end_current), gross_expr_current),
                    else_=0,
                )
            ).label("current_gross_profit"),
            # Totais do período anterior
            func.sum(
                case(
                    (models.Order.created_at.between(start_previous, end_previous), models.Order.total_price),
                    else_=0,
                )
            ).label("previous_total_value"),
            func.count(
                case(
                    (models.Order.created_at.between(start_previous, end_previous), models.Order.id),
                    else_=None,
                )
            ).label("previous_sales_count"),
            func.sum(
                case(
                    (models.Order.created_at.between(start_previous, end_previous), gross_expr_previous),
                    else_=0,
                )
            ).label("previous_gross_profit"),
        )
        .join(models.OrderProduct, models.Order.id == models.OrderProduct.order_id)
        .join(models.Product, models.OrderProduct.product_id == models.Product.id)
        .filter(
            models.Order.store_id == store_id,
            models.Order.order_status == COMPLETED,
            # limita aos dois períodos para otimizar
            (models.Order.created_at.between(start_current, end_current))
            | (models.Order.created_at.between(start_previous, end_previous)),
        )
        .first()
    )

    # Trata None com zeros
    current_total_value = _to_real(getattr(agg, "current_total_value", 0))
    previous_total_value = _to_real(getattr(agg, "previous_total_value", 0))
    current_sales_count = int(getattr(agg, "current_sales_count", 0) or 0)
    previous_sales_count = int(getattr(agg, "previous_sales_count", 0) or 0)
    current_gross_profit = _to_real(getattr(agg, "current_gross_profit", 0))
    previous_gross_profit = _to_real(getattr(agg, "previous_gross_profit", 0))

    summary = DailySummarySchema(
        completed_sales=_build_comparative_metric(current_sales_count, previous_sales_count),
        total_value=_build_comparative_metric(current_total_value, previous_total_value),
        average_ticket=_build_comparative_metric(
            (current_total_value / current_sales_count) if current_sales_count else 0.0,
            (previous_total_value / previous_sales_count) if previous_sales_count else 0.0,
        ),
    )
    gross_profit = _build_comparative_metric(current_gross_profit, previous_gross_profit)
    return summary, gross_profit


# src/api/admin/services/performance_service.py

def _calc_customer_analytics(
        db: Session,
        store_id: int,
        start_current: datetime,
        end_current: datetime,
        start_previous: datetime,
        end_previous: datetime,
) -> CustomerAnalyticsSchema:
    """
    Calcula novos vs recorrentes para os períodos atual e comparativo.
    """

    def _period_counts(start_dt: datetime, end_dt: datetime) -> Tuple[int, int]:
        """Helper que calcula as contagens para um único intervalo de datas."""

        # 1. Pega os IDs únicos de todos os clientes que fizeram pedidos no período
        customer_ids_in_period = {
            row.customer_id
            for row in db.query(models.Order.customer_id)
            .filter(
                models.Order.store_id == store_id,
                # ✅ ALTERADO: Usa o intervalo de datas em vez de um único dia
                models.Order.created_at.between(start_dt, end_dt),
                models.Order.customer_id.isnot(None),
            )
            .distinct()
            .all()
        }

        if not customer_ids_in_period:
            return 0, 0

        # 2. Desses clientes, conta quantos foram 'criados' (fizeram a primeira compra) dentro do mesmo período
        new_customers_count = (
                db.query(func.count(models.StoreCustomer.customer_id))
                .filter(
                    models.StoreCustomer.store_id == store_id,
                    models.StoreCustomer.customer_id.in_(customer_ids_in_period),
                    # ✅ ALTERADO: Verifica se a data de criação está no intervalo
                    models.StoreCustomer.created_at.between(start_dt, end_dt),
                )
                .scalar()
                or 0
        )

        returning_customers_count = max(len(customer_ids_in_period) - new_customers_count, 0)
        return new_customers_count, returning_customers_count

    # Calcula para o período atual
    current_new, current_returning = _period_counts(start_current, end_current)
    # Calcula para o período anterior
    previous_new, previous_returning = _period_counts(start_previous, end_previous)

    # Monta a resposta final com a comparação
    return CustomerAnalyticsSchema(
        new_customers=_build_comparative_metric(current_new, previous_new),
        returning_customers=_build_comparative_metric(current_returning, previous_returning),
    )

def _sales_by_hour(
    db: Session, store_id: int, start_dt: datetime, end_dt: datetime
) -> list[SalesByHourSchema]:
    COMPLETED = OrderStatus.DELIVERED.value
    rows = (
        _orders_base_query(db, store_id, start_dt, end_dt, COMPLETED)
        .with_entities(
            func.extract("hour", models.Order.created_at).label("hour"),
            func.sum(models.Order.total_price).label("total_value"),
        )
        .group_by("hour")
        .order_by("hour")
        .all()
    )
    return [SalesByHourSchema(hour=int(r.hour), totalValue=_to_real(r.total_value)) for r in rows]


def _payment_methods(
    db: Session, store_id: int, start_dt: datetime, end_dt: datetime
) -> list[PaymentMethodSummarySchema]:
    """
    Soma por método de pagamento (nome e ícone da plataforma).
    Mantém os joins conforme seu modelo (Order -> payment_method -> platform_method).
    """
    COMPLETED = OrderStatus.DELIVERED.value

    rows = (
        _orders_base_query(db, store_id, start_dt, end_dt, COMPLETED)
        .join(models.Order.payment_method)  # relacionamento esperado
        .join(models.StorePaymentMethodActivation.platform_method)
        .with_entities(
            models.PlatformPaymentMethod.name.label("name"),
            models.PlatformPaymentMethod.icon_key.label("icon_key"),
            func.sum(models.Order.total_price).label("total_value"),
            func.count(models.Order.id).label("count"),
        )
        .group_by(models.PlatformPaymentMethod.name, models.PlatformPaymentMethod.icon_key)
        .all()
    )
    return [
        PaymentMethodSummarySchema(
            method_name=r.name,
            method_icon=r.icon_key,
            total_value=_to_real(r.total_value),
            transaction_count=int(r.count or 0),
        )
        for r in rows
    ]


def _top_products(
    db: Session, store_id: int, start_dt: datetime, end_dt: datetime
) -> list[TopSellingProductSchema]:
    COMPLETED = OrderStatus.DELIVERED.value
    rows = (
        db.query(
            models.Product.id.label("pid"),
            models.Product.name.label("pname"),
            func.sum(models.OrderProduct.quantity).label("qty"),
            func.sum(models.OrderProduct.price * models.OrderProduct.quantity).label("value"),
        )
        .join(models.OrderProduct, models.Product.id == models.OrderProduct.product_id)
        .join(models.Order, models.OrderProduct.order_id == models.Order.id)
        .filter(
            models.Order.store_id == store_id,
            models.Order.created_at.between(start_dt, end_dt),
            models.Order.order_status == COMPLETED,
        )
        .group_by(models.Product.id, models.Product.name)
        .order_by(func.sum(models.OrderProduct.quantity).desc())
        .limit(5)
        .all()
    )
    return [
        TopSellingProductSchema(
            product_id=r.pid,
            product_name=r.pname,
            quantity_sold=int(r.qty or 0),
            total_value=_to_real(r.value),
        )
        for r in rows
    ]


def _order_status_counts(
    db: Session, store_id: int, start_dt: datetime, end_dt: datetime
) -> OrderStatusCountSchema:
    rows = (
        _orders_base_query(db, store_id, start_dt, end_dt)
        .with_entities(models.Order.order_status, func.count(models.Order.id).label("count"))
        .group_by(models.Order.order_status)
        .all()
    )
    counts = {r.order_status: int(r.count or 0) for r in rows}
    return OrderStatusCountSchema(
        concluidos=counts.get(OrderStatus.DELIVERED.value, 0),
        cancelados=counts.get(OrderStatus.CANCELED.value, 0),
        pendentes=counts.get(OrderStatus.PENDING.value, 0),
    )


def _top_addons(
    db: Session, store_id: int, start_dt: datetime, end_dt: datetime
) -> list[TopAddonSchema]:
    COMPLETED = OrderStatus.DELIVERED.value
    rows = (
        db.query(
            models.OrderVariantOption.name.label("name"),
            func.sum(models.OrderVariantOption.quantity).label("qty"),
            func.sum(models.OrderVariantOption.price * models.OrderVariantOption.quantity).label("value"),
        )
        .join(models.OrderVariant, models.OrderVariantOption.order_variant_id == models.OrderVariant.id)
        .join(models.OrderProduct, models.OrderVariant.order_product_id == models.OrderProduct.id)
        .join(models.Order, models.OrderProduct.order_id == models.Order.id)
        .filter(
            models.Order.store_id == store_id,
            models.Order.created_at.between(start_dt, end_dt),
            models.Order.order_status == COMPLETED,
        )
        .group_by(models.OrderVariantOption.name)
        .order_by(func.sum(models.OrderVariantOption.quantity).desc())
        .limit(5)
        .all()
    )
    return [
        TopAddonSchema(
            addon_name=r.name,
            quantity_sold=int(r.qty or 0),
            total_value=_to_real(r.value),
        )
        for r in rows
    ]


def _coupon_performance(
    db: Session, store_id: int, start_dt: datetime, end_dt: datetime
) -> list[CouponPerformanceSchema]:
    """
    Performance de cupons no período.
    Receita considera discounted_total_price se existir, senão total_price.
    """
    # cria a expressão de receita líquida (fallback para total_price)
    revenue_expr = func.coalesce(models.Order.discounted_total_price, models.Order.total_price)

    rows = (
        db.query(
            models.Coupon.code.label("code"),
            func.count(models.CouponUsage.id).label("uses"),
            func.sum(models.Order.discount_amount).label("discount"),
            func.sum(revenue_expr).label("revenue"),
        )
        .join(models.CouponUsage, models.Coupon.id == models.CouponUsage.coupon_id)
        .join(models.Order, models.CouponUsage.order_id == models.Order.id)
        .filter(
            models.Order.store_id == store_id,
            models.Order.created_at.between(start_dt, end_dt),
        )
        .group_by(models.Coupon.code)
        .all()
    )
    return [
        CouponPerformanceSchema(
            coupon_code=r.code,
            times_used=int(r.uses or 0),
            total_discount=_to_real(r.discount),
            revenue_generated=_to_real(r.revenue),
        )
        for r in rows
    ]


def _category_performance(
    db: Session, store_id: int, start_dt: datetime, end_dt: datetime
) -> list[CategoryPerformanceSchema]:
    COMPLETED = OrderStatus.DELIVERED.value
    rows = (
        db.query(
            models.Category.id.label("cat_id"),
            models.Category.name.label("cat_name"),
            func.sum(models.OrderProduct.quantity).label("items_sold"),
            func.sum(models.OrderProduct.price * models.OrderProduct.quantity).label("total_value"),
            func.sum(
                (models.OrderProduct.price - func.coalesce(models.Product.cost_price, 0)) * models.OrderProduct.quantity
            ).label("gross_profit"),
        )
        .join(models.Product, models.Category.id == models.Product.category_id)
        .join(models.OrderProduct, models.Product.id == models.OrderProduct.product_id)
        .join(models.Order, models.OrderProduct.order_id == models.Order.id)
        .filter(
            models.Order.store_id == store_id,
            models.Order.created_at.between(start_dt, end_dt),
            models.Order.order_status == COMPLETED,
        )
        .group_by(models.Category.id, models.Category.name)
        .order_by(func.sum(models.OrderProduct.price * models.OrderProduct.quantity).desc())
        .all()
    )
    return [
        CategoryPerformanceSchema(
            category_id=r.cat_id,
            category_name=r.cat_name,
            items_sold=int(r.items_sold or 0),
            total_value=_to_real(r.total_value),
            gross_profit=_to_real(r.gross_profit),
        )
        for r in rows
    ]


def _product_sales_funnel(
        db: Session, store_id: int, start_dt: datetime, end_dt: datetime
) -> list[ProductFunnelSchema]:
    COMPLETED = OrderStatus.DELIVERED.value

    # 1. Obter dados de VENDAS de produtos no período
    sales_results = (
        db.query(
            models.Product.id,
            models.Product.name,
            func.count(models.OrderProduct.id).label("sales_count"),
            func.sum(models.OrderProduct.quantity).label("quantity_sold"),
        )
        .join(models.OrderProduct, models.Product.id == models.OrderProduct.product_id)
        .join(models.Order, models.OrderProduct.order_id == models.Order.id)
        .filter(
            models.Order.store_id == store_id,
            models.Order.created_at.between(start_dt, end_dt),
            models.Order.order_status == COMPLETED,
        )
        .group_by(models.Product.id, models.Product.name)
        .all()
    )
    sales_data = {row.id: row for row in sales_results}

    # 2. Obter dados de VISUALIZAÇÕES de produtos no período
    view_results = (
        db.query(
            models.ProductView.product_id,
            func.count(models.ProductView.id).label("view_count"),
        )
        .filter(
            models.ProductView.store_id == store_id,
            models.ProductView.viewed_at.between(start_dt, end_dt),
        )
        .group_by(models.ProductView.product_id)
        .all()
    )
    views_data = {row.product_id: row.view_count for row in view_results}

    # 3. Combinar os dados em Python
    funnel_list = []
    all_product_ids = set(sales_data.keys()) | set(views_data.keys())

    # Precisamos dos nomes de todos os produtos envolvidos
    product_names = {p.id: p.name for p in
                     db.query(models.Product.id, models.Product.name).filter(models.Product.id.in_(all_product_ids))}

    for pid in all_product_ids:
        sales = sales_data.get(pid)
        views = views_data.get(pid, 0)

        sales_count = int(sales.sales_count) if sales else 0
        quantity_sold = int(sales.quantity_sold) if sales else 0

        conversion_rate = (sales_count / views) * 100 if views > 0 else 0.0

        funnel_list.append(
            ProductFunnelSchema(
                product_id=pid,
                product_name=product_names.get(pid, "Produto Removido"),
                view_count=views,
                sales_count=sales_count,
                quantity_sold=quantity_sold,
                conversion_rate=conversion_rate,
            )
        )

    # Ordena a lista pelos produtos mais vistos
    return sorted(funnel_list, key=lambda p: p.view_count, reverse=True)


# ✅ CRIE ESTA NOVA FUNÇÃO HELPER
def get_today_summary(db: Session, store_id: int) -> TodaySummarySchema:
    """Calcula um resumo rápido das vendas concluídas do dia de operação."""
    # O iFood considera o dia das 05:00 de hoje até 04:59 de amanhã.
    # Vamos simular essa lógica.
    now = datetime.now()
    start_of_operation_day = now.replace(hour=5, minute=0, second=0, microsecond=0)
    if now.hour < 5:  # Se for antes das 5 da manhã, pega o dia anterior
        start_of_operation_day -= timedelta(days=1)
    end_of_operation_day = start_of_operation_day + timedelta(days=1)

    COMPLETED = OrderStatus.DELIVERED.value

    summary_metrics = (
        db.query(
            func.count(models.Order.id).label("count"),
            func.sum(models.Order.total_price).label("value"),
        )
        .filter(
            models.Order.store_id == store_id,
            models.Order.order_status == COMPLETED,
            models.Order.created_at.between(start_of_operation_day, end_of_operation_day),
        )
        .one()
    )

    count = summary_metrics.count or 0
    value = _to_real(summary_metrics.value)
    ticket = (value / count) if count > 0 else 0.0

    return TodaySummarySchema(
        completed_sales=count,
        total_value=value,
        average_ticket=ticket,
    )



def _get_daily_trend(db: Session, store_id: int, start_dt: datetime, end_dt: datetime) -> list[DailyTrendPointSchema]:
    COMPLETED = OrderStatus.DELIVERED.value

    # Query principal que agrupa os pedidos por dia
    daily_sales = db.query(
        func.date(models.Order.created_at).label("day"),
        func.count(models.Order.id).label("sales_count"),
        func.sum(models.Order.total_price).label("total_value")
    ).filter(
        models.Order.store_id == store_id,
        models.Order.order_status == COMPLETED,
        models.Order.created_at.between(start_dt, end_dt)
    ).group_by(func.date(models.Order.created_at)).all()

    # (Lógica para novos clientes por dia - pode ser otimizada depois)
    # Por enquanto, vamos focar nas métricas de vendas.

    trend_points = []
    for row in daily_sales:
        count = row.sales_count or 0
        value = _to_real(row.total_value)
        ticket = (value / count) if count > 0 else 0.0
        trend_points.append(DailyTrendPointSchema(
            date=row.day,
            sales_count=count,
            total_value=value,
            average_ticket=ticket,
            new_customers=0  # Placeholder por enquanto
        ))

    return trend_points

def get_store_performance_for_date(db: Session, store_id: int, start_date: date, end_date: date) -> StorePerformanceSchema:
    """
    Calcula o painel de performance para um intervalo de datas,
    comparando com o período anterior de mesma duração.
    """
    # --- 1. Definir Períodos de Tempo ---
    period_duration = (end_date - start_date).days + 1
    comparison_start_date = start_date - timedelta(days=period_duration)
    comparison_end_date = start_date - timedelta(days=1)

    # Converte para datetime para as queries
    start_current, end_current = _time_range_for_day(start_date)[0], _time_range_for_day(end_date)[1]
    start_previous, end_previous = _time_range_for_day(comparison_start_date)[0], _time_range_for_day(comparison_end_date)[1]


    # 1) Vendas / Ticket / Lucro
    summary, gross_profit = _calc_sales_and_profit(
        db, store_id, start_current, end_current, start_previous, end_previous
    )

    # 2) Clientes
    customer_analytics = _calc_customer_analytics(db, store_id, start_current, end_current, start_previous, end_previous)

    # 3) Gráficos e breakdowns do dia atual
    sales_by_hour = _sales_by_hour(db, store_id, start_current, end_current)
    payment_methods = _payment_methods(db, store_id, start_current, end_current)
    top_selling_products = _top_products(db, store_id, start_current, end_current)
    order_status_counts = _order_status_counts(db, store_id, start_current, end_current)
    top_selling_addons = _top_addons(db, store_id, start_current, end_current)
    coupon_performance = _coupon_performance(db, store_id, start_current, end_current)

    category_performance = _category_performance(db, store_id, start_current, end_current)

    product_funnel = _product_sales_funnel(db, store_id, start_current, end_current)

    daily_trend = _get_daily_trend(db, store_id, start_current, end_current)

    return StorePerformanceSchema(
        query_date=end_date,  # Podemos usar a data final como referência
        comparison_date=comparison_end_date,
        summary=summary,
        gross_profit=gross_profit,
        customer_analytics=customer_analytics,
        sales_by_hour=sales_by_hour,
        payment_methods=payment_methods,
        top_selling_products=top_selling_products,
        order_status_counts=order_status_counts,
        top_selling_addons=top_selling_addons,
        coupon_performance=coupon_performance,
        category_performance=category_performance,
        product_funnel=product_funnel,
        daily_trend=daily_trend
    )
