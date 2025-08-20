import asyncio
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from typing import List, Optional

from src.api.admin.services.product_analytic_services import _process_low_stock, _process_top_products, \
    _process_low_turnover, _fetch_product_data_from_db
from src.api.schemas.insights_schema import DashboardInsight, LowStockInsightDetails, LowMoverInsightDetails



class InsightsService:

    @staticmethod
    def _generate_low_stock_insight(
            all_products_data: List[dict]
    ) -> Optional[DashboardInsight]:
        """
        Gera um insight para o item mais crítico com estoque baixo.
        A prioridade é para itens que são "top de vendas".
        """
        low_stock_items = _process_low_stock(all_products_data)
        if not low_stock_items:
            return None

        top_products = _process_top_products(all_products_data)
        top_product_ids = {p.product_id for p in top_products}

        # Prioriza o item de baixo estoque que também é um dos mais vendidos
        critical_item = None
        for item in low_stock_items:
            if item.product_id in top_product_ids:
                critical_item = item
                break

        # Se nenhum "top" está com estoque baixo, pega o primeiro da lista
        if not critical_item:
            critical_item = low_stock_items[0]

        details = LowStockInsightDetails(
            product_id=critical_item.product_id,
            product_name=critical_item.name,
            current_stock=critical_item.stock_quantity,
            min_stock=critical_item.minimum_stock_level,
            is_top_seller=(critical_item.product_id in top_product_ids)
        )

        return DashboardInsight(
            insight_type="LOW_STOCK",
            title="⚠️ Alerta de Estoque Baixo",
            message=f"Seu produto '{details.product_name}' está acabando! Apenas {details.current_stock} unidades restantes.",
            details=details
        )

    @staticmethod
    def _generate_low_mover_insight(
            all_products_data: List[dict]
    ) -> Optional[DashboardInsight]:
        """
        Gera um insight para um item que não vende há muito tempo.
        """
        today = datetime.now()
        low_turnover_items = _process_low_turnover(all_products_data, today, period_in_days=30)

        if not low_turnover_items:
            return None

        # Pega o item que está há mais tempo sem vender para destacar
        stale_item = max(low_turnover_items, key=lambda item: item.days_since_last_sale)

        details = LowMoverInsightDetails(
            product_id=stale_item.product_id,
            product_name=stale_item.name,
            days_since_last_sale=stale_item.days_since_last_sale
        )

        return DashboardInsight(
            insight_type="LOW_MOVER_ITEM",
            title="📈 Oportunidade de Otimização",
            message=f"O item '{details.product_name}' não vende há {details.days_since_last_sale} dias. Considere criar uma promoção.",
            details=details
        )

    @staticmethod
    async def generate_dashboard_insights(db: Session, store_id: int) -> List[DashboardInsight]:
        """
        Orquestra a geração de todos os insights para o dashboard.
        """
        insights = []

        # 1. Busca os dados base uma única vez
        start_date = datetime.now() - timedelta(days=30)
        # Reutilizamos a função de busca que já existe e a executamos em uma thread
        all_products_data = await asyncio.to_thread(_fetch_product_data_from_db, db, store_id, start_date)

        # 2. Gera cada insight e adiciona à lista
        low_stock_insight = InsightsService._generate_low_stock_insight(all_products_data)
        if low_stock_insight:
            insights.append(low_stock_insight)

        low_mover_insight = InsightsService._generate_low_mover_insight(all_products_data)
        if low_mover_insight:
            insights.append(low_mover_insight)

        return insights