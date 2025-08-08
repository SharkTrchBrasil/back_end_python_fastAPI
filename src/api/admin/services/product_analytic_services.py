# Crie este novo arquivo: src/api/admin/logic/analytic_logic.py

from datetime import datetime, timedelta
from typing import List, Dict
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

# Importe seus schemas Pydantic que já criamos
from src.api.admin.schemas.analytic_produc_schema import (
    ProductAnalyticsResponse, TopProductItem, LowTurnoverItem,
    LowStockItem, AbcAnalysis, AbcItem
)


# --- FUNÇÕES AUXILIARES (Lógica de processamento) ---
# (Estas são as mesmas que estavam dentro da classe, mas agora são funções normais)

def _process_top_products(products: List[Dict]) -> List[TopProductItem]:
    """Processa e retorna os 10 produtos mais vendidos."""
    products_with_revenue = [p for p in products if p.get('revenue', 0) > 0]
    sorted_products = sorted(products_with_revenue, key=lambda p: p['revenue'], reverse=True)
    return [TopProductItem(**p) for p in sorted_products[:10]]


def _process_low_turnover(products: List[Dict], today: datetime, period_in_days: int) -> List[LowTurnoverItem]:
    """Encontra produtos que não vendem há mais tempo que o período analisado."""
    results = []
    for p in products:
        days_since = 999
        if p.get('last_sale_date'):
            days_since = (today.date() - p['last_sale_date']).days

        if not p.get('last_sale_date') or days_since > period_in_days:
            results.append({**p, 'days_since_last_sale': days_since})
    return [LowTurnoverItem(**p) for p in results]


def _process_low_stock(products: List[Dict]) -> List[LowStockItem]:
    """Filtra produtos cujo estoque está no nível mínimo ou abaixo."""
    results = [
        p for p in products
        if p.get('stock_quantity') is not None
           and p.get('minimum_stock_level') is not None
           and p.get('stock_quantity') <= p.get('minimum_stock_level')
    ]
    return [LowStockItem(**p) for p in results]


def _calculate_abc_analysis(products: List[Dict]) -> AbcAnalysis:
    """Calcula a Curva ABC de faturamento dos produtos."""
    revenue_products = sorted([p for p in products if p.get('revenue', 0) > 0], key=lambda p: p['revenue'],
                              reverse=True)

    if not revenue_products:
        return AbcAnalysis(class_a_items=[], class_b_items=[], class_c_items=[])

    grand_total_revenue = sum(p['revenue'] for p in revenue_products)
    if grand_total_revenue == 0:
        return AbcAnalysis(class_a_items=[], class_b_items=[], class_c_items=[])

    class_a, class_b, class_c = [], [], []
    cumulative_revenue = 0.0
    for p in revenue_products:
        cumulative_revenue += p['revenue']
        cumulative_percentage = (cumulative_revenue / grand_total_revenue) * 100

        abc_item_data = {
            'product_id': p['product_id'],
            'name': p['name'],
            'revenue': p['revenue'],
            'contribution_percentage': (p['revenue'] / grand_total_revenue) * 100
        }

        if cumulative_percentage <= 80:
            class_a.append(AbcItem(**abc_item_data))
        elif cumulative_percentage <= 95:
            class_b.append(AbcItem(**abc_item_data))
        else:
            class_c.append(AbcItem(**abc_item_data))

    return AbcAnalysis(class_a_items=class_a, class_b_items=class_b, class_c_items=class_c)



# Em src/api/admin/logic/analytic_logic.py

async def get_product_analytics_for_store(db: AsyncSession, store_id: int,
                                          period_in_days: int = 30) -> ProductAnalyticsResponse:
    """
    Orquestra a busca e o processamento de todos os dados de análise de produtos.
    """
    start_date = datetime.now() - timedelta(days=period_in_days)
    today = datetime.now()

    # 1. A CONSULTA INTELIGENTE E ÚNICA
    query = f"""
    WITH SalesSummary AS (
        SELECT
            oi.product_id,
            SUM(oi.price * oi.quantity) AS total_revenue,
            SUM(oi.quantity) AS units_sold,
            MAX(DATE(o.created_at)) AS last_sale_date,
            SUM((oi.price - p.cost_price) * oi.quantity) AS total_profit
        FROM
            order_products oi -- ✅ NOME DA TABELA CORRIGIDO AQUI
        JOIN
            orders o ON o.id = oi.order_id
        JOIN
            products p ON p.id = oi.product_id
        WHERE
            o.store_id = :store_id
            AND o.created_at >= :start_date
        GROUP BY
            oi.product_id, p.cost_price
    )
    SELECT
        p.id AS product_id,
        p.name,
        p.image_url,
        p.stock_quantity,
        p.min_stock AS minimum_stock_level,
        COALESCE(ss.total_revenue, 0) AS revenue,
        COALESCE(ss.units_sold, 0) AS units_sold,
        ss.last_sale_date,
        COALESCE(ss.total_profit, 0) AS profit
    FROM
        products p
    LEFT JOIN
        SalesSummary ss ON p.id = ss.product_id
    WHERE
        p.store_id = :store_id
        AND p.control_stock = TRUE;
    """

    # Executando a query de verdade
    result = await db.execute(text(query), {"store_id": store_id, "start_date": start_date})
    enriched_products = [dict(row) for row in result.mappings()]

    # O resto da função continua exatamente igual, pois já estava correta.
    top_products = _process_top_products(enriched_products)
    low_turnover_items = _process_low_turnover(enriched_products, today, period_in_days)
    low_stock_items = _process_low_stock(enriched_products)
    abc_analysis = _calculate_abc_analysis(enriched_products)

    return ProductAnalyticsResponse(
        top_products=top_products,
        low_turnover_items=low_turnover_items,
        low_stock_items=low_stock_items,
        abc_analysis=abc_analysis,
    )