from datetime import date, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import func, extract

from src.core import models
from src.api.schemas.analytics.dashboard import (
    DashboardDataSchema,
    DashboardKpiSchema,
    SalesDataPointSchema,
    TopItemSchema,
    PaymentMethodSummarySchema, MonthlyDataPoint, OrderTypeSummarySchema,
)
from src.core.utils.enums import OrderStatus


def get_dashboard_data_for_period(db: Session, store_id: int, start_date: date, end_date: date) -> DashboardDataSchema:
    """
    Função central que calcula todos os dados do dashboard para um determinado período.
    Esta função contém toda a lógica que estava na sua rota GET /dashboard.
    """
    # Filtro base para pedidos concluídos no período
    base_order_filter = (
        models.Order.store_id == store_id,
        models.Order.created_at.between(start_date, end_date + timedelta(days=1)),  # Inclui o dia de hoje
        models.Order.order_status == OrderStatus.DELIVERED
    )

    # --- 1. Cálculo dos KPIs ---

    kpi_query = db.query(
        func.sum(models.Order.discounted_total_price).label("total_revenue"),
        func.count(models.Order.id).label("transaction_count"),
        func.sum(models.Order.cashback_amount_generated).label("total_cashback")  # Assumindo que você tem essa coluna
    ).filter(*base_order_filter).first()

    current_revenue = (kpi_query.total_revenue or 0)
    transaction_count = (kpi_query.transaction_count or 0)
    total_cashback = (kpi_query.total_cashback or 0)
    average_ticket = (current_revenue / transaction_count) if transaction_count > 0 else 0.0

    # ✅ CORREÇÃO: CÁLCULO DE NOVOS CLIENTES PARA O PERÍODO ATUAL
    first_order_subquery = db.query(
        models.Order.customer_id,
        func.min(models.Order.created_at).label("first_order_date")
    ).filter(models.Order.store_id == store_id).group_by(models.Order.customer_id).subquery()

    new_customers_count = db.query(func.count(first_order_subquery.c.customer_id)).filter(
        first_order_subquery.c.first_order_date.between(start_date, end_date + timedelta(days=1))
    ).scalar() or 0

    # --- CÁLCULO DA TAXA DE RETENÇÃO ---
    # Subquery para contar o número de pedidos por cliente (considerando todos os pedidos da loja)
    order_count_per_customer_subquery = (
        db.query(
            models.Order.customer_id,
            func.count(models.Order.id).label("order_count")
        )
        .filter(models.Order.store_id == store_id)
        .group_by(models.Order.customer_id)
        .subquery()
    )

    # Contamos quantos clientes têm mais de 1 pedido (recorrentes)
    returning_customers_count = db.query(func.count(order_count_per_customer_subquery.c.customer_id)).filter(
        order_count_per_customer_subquery.c.order_count > 1
    ).scalar() or 0

    # ✅ CORREÇÃO: O total de clientes da loja é o número total de
    # entradas na nossa subquery (clientes com pelo menos 1 pedido).
    total_store_customers_count = db.query(func.count(order_count_per_customer_subquery.c.customer_id)).scalar() or 0

    # Agora o cálculo da retenção é preciso para a loja
    retention_rate = (
                                 returning_customers_count / total_store_customers_count) * 100 if total_store_customers_count > 0 else 0.0





    # --- Cálculo da Variação de Receita (Comparação com período anterior) ---
    period_duration = (end_date - start_date).days
    previous_start_date = start_date - timedelta(days=period_duration + 1)
    previous_end_date = start_date - timedelta(days=1)

    previous_revenue = db.query(func.sum(models.Order.discounted_total_price)).filter(
        models.Order.store_id == store_id,
        models.Order.created_at.between(previous_start_date, previous_end_date + timedelta(days=1)),
        models.Order.order_status == OrderStatus.DELIVERED
    ).scalar() or 0

    if previous_revenue > 0:
        revenue_change_percentage = ((current_revenue - previous_revenue) / previous_revenue) * 100
    else:
        revenue_change_percentage = 100.0 if current_revenue > 0 else 0.0

        # ✅ CORREÇÃO NA CRIAÇÃO DO OBJETO kpis
    kpis = DashboardKpiSchema(
        total_revenue=current_revenue / 100,
        transaction_count=transaction_count,
        average_ticket=average_ticket / 100,
        new_customers=new_customers_count,  # <-- Usa a contagem correta
        total_cashback=total_cashback / 100,
        total_spent=current_revenue / 100,
        revenue_change_percentage=revenue_change_percentage,
        revenue_is_up=current_revenue > previous_revenue,
        retention_rate=retention_rate,  # ✅ NOVO DADO

    )

    # --- 2. DADOS PARA O GRÁFICO DE NOVOS CLIENTES POR MÊS ---
    # ✅ LÓGICA REINSERIDA AQUI
    six_months_ago = end_date - timedelta(days=180)

    # Esta query busca a data do primeiro pedido de cada cliente na loja
    first_order_monthly_subquery = db.query(
        models.Order.customer_id,
        func.min(models.Order.created_at).label("first_order_date")
    ).filter(models.Order.store_id == store_id).group_by(models.Order.customer_id).subquery()

    # Agora contamos quantos "primeiros pedidos" aconteceram em cada mês
    monthly_customers_data = (
        db.query(
            extract('year', first_order_monthly_subquery.c.first_order_date).label('year'),
            extract('month', first_order_monthly_subquery.c.first_order_date).label('month'),
            func.count(first_order_monthly_subquery.c.customer_id).label('count')
        )
        .filter(first_order_monthly_subquery.c.first_order_date >= six_months_ago)
        .group_by('year', 'month')
        .order_by('year', 'month')
        .all()
    )

    new_customers_over_time = []
    month_map = {1: "Jan", 2: "Fev", 3: "Mar", 4: "Abr", 5: "Mai", 6: "Jun", 7: "Jul", 8: "Ago", 9: "Set", 10: "Out",
                 11: "Nov", 12: "Dez"}
    for year, month, count in monthly_customers_data:
        new_customers_over_time.append(
            MonthlyDataPoint(month=month_map.get(month, '?'), count=count)
        )

    # --- 2. Dados para o Gráfico de Vendas ---
    sales_over_time_query = db.query(
        func.date(models.Order.created_at).label("period"),
        func.sum(models.Order.discounted_total_price).label("revenue")
    ).filter(*base_order_filter).group_by(
        func.date(models.Order.created_at)
    ).order_by(func.date(models.Order.created_at)).all()

    sales_over_time = [
        SalesDataPointSchema(period=row.period, revenue=row.revenue / 100)
        for row in sales_over_time_query
    ]

    # --- 3. Top 5 Produtos ---
    top_products_query = db.query(
        models.OrderProduct.name,
        func.sum(models.OrderProduct.quantity).label("count"),
        func.sum(models.OrderProduct.price * models.OrderProduct.quantity).label("revenue")
    ).join(models.Order).filter(*base_order_filter).group_by(
        models.OrderProduct.name
    ).order_by(func.sum(models.OrderProduct.quantity).desc()).limit(5).all()

    top_products = [TopItemSchema(name=row.name, count=row.count, revenue=(row.revenue or 0) / 100) for row in
                    top_products_query]

    # --- 6. TOP PRODUTO POR RECEITA ---
    top_product_revenue_query = db.query(
        models.OrderProduct.name,
        func.sum(models.OrderProduct.price * models.OrderProduct.quantity).label("revenue")
    ).join(models.Order).filter(*base_order_filter).group_by(
        models.OrderProduct.name
    ).order_by(func.sum(models.OrderProduct.price * models.OrderProduct.quantity).desc()).first()

    top_product_by_revenue = None
    if top_product_revenue_query:
        top_product_by_revenue = TopItemSchema(
            name=top_product_revenue_query.name,
            count=0,  # A contagem não é relevante aqui, mas o schema exige
            revenue=(top_product_revenue_query.revenue or 0) / 100
        )




    # --- 4. Top 5 Categorias ---
    # (Requer que OrderProduct tenha uma relação com Product, que tem uma relação com Category)
    # --- 4. Top 5 Categorias (CORRIGIDA para N-N) ---
    top_categories_query = db.query(
        models.Category.name,
        func.sum(models.OrderProduct.quantity).label("count"),
        func.sum(models.OrderProduct.price * models.OrderProduct.quantity).label("revenue")
    ).select_from(models.OrderProduct) \
        .join(models.Order, models.OrderProduct.order_id == models.Order.id) \
        .join(models.Product, models.OrderProduct.product_id == models.Product.id) \
        .join(models.ProductCategoryLink, models.Product.id == models.ProductCategoryLink.product_id) \
        .join(models.Category, models.ProductCategoryLink.category_id == models.Category.id) \
        .filter(*base_order_filter) \
        .group_by(models.Category.name) \
        .order_by(func.sum(models.OrderProduct.quantity).desc()) \
        .limit(5).all()

    top_categories = [TopItemSchema(name=row.name, count=row.count, revenue=(row.revenue or 0) / 100) for row in
                      top_categories_query]

    order_type_query = db.query(
        models.Order.order_type,
        func.count(models.Order.id).label("count")
    ).filter(*base_order_filter).group_by(models.Order.order_type).all()

    order_type_distribution = [
        OrderTypeSummarySchema(order_type=row.order_type, count=row.count)  # Usamos .name se for um Enum
        for row in order_type_query
    ]


    # --- 5. Resumo por Método de Pagamento ---

    payment_methods_query = db.query(
        models.PlatformPaymentMethod.name.label("method_name"),
        func.sum(models.Order.discounted_total_price).label("total_amount")
    ).join(
        models.Order.payment_method  # relacionamento com StorePaymentMethodActivation
    ).join(
        models.StorePaymentMethodActivation.platform_method  # relacionamento com PlatformPaymentMethod
    ).filter(
        *base_order_filter
    ).group_by(
        models.PlatformPaymentMethod.name
    ).all()

    payment_methods = [
        PaymentMethodSummarySchema(method_name=row.method_name, total_amount=row.total_amount / 100)
        for row in payment_methods_query
    ]

    # --- Monta a Resposta Final ---
    return DashboardDataSchema(
        kpis=kpis,
        sales_over_time=sales_over_time,
        top_products=top_products,
        top_categories=top_categories,
        payment_methods=payment_methods,
        new_customers_over_time=new_customers_over_time,
        user_cards=[],
        currency_balances=[],
        top_product_by_revenue=top_product_by_revenue,  # ✅ NOVO DADO
        order_type_distribution=order_type_distribution,
    )