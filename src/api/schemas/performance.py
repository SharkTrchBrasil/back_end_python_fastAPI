# src/api/schemas/performance.py

from pydantic import BaseModel, Field
from datetime import date
from typing import List, Optional


class DailySummarySchema(BaseModel):
    """Resumo dos principais KPIs do dia."""
    completed_sales: int = Field(..., description="Número de vendas concluídas (status 'delivered' ou similar).")
    total_value: float = Field(..., description="Soma do valor total dos pedidos concluídos.")
    average_ticket: float = Field(..., description="Ticket médio (Valor Total / Vendas Concluídas).")


class SalesByHourSchema(BaseModel):
    """Estrutura para o gráfico de vendas por hora."""
    hour: int
    total_value: float = Field(..., alias="totalValue")  # Alias para camelCase no JSON

    class Config:
        populate_by_name = True  # Permite usar o alias


class PaymentMethodSummarySchema(BaseModel):
    """Estrutura para o gráfico de formas de pagamento."""
    method_name: str
    total_value: float
    method_icon: Optional[str] = None  #
    transaction_count: int


class TopSellingProductSchema(BaseModel):
    """Estrutura para a lista de produtos mais vendidos."""
    product_id: int
    product_name: str
    quantity_sold: int
    total_value: float


class CustomerAnalyticsSchema(BaseModel):
    """Dados sobre clientes novos vs. recorrentes."""
    new_customers: int
    returning_customers: int


class StorePerformanceSchema(BaseModel):
    """O objeto de resposta completo para a página de desempenho."""
    query_date: date
    summary: DailySummarySchema
    sales_by_hour: List[SalesByHourSchema]
    payment_methods: List[PaymentMethodSummarySchema]
    top_selling_products: List[TopSellingProductSchema]
    customer_analytics: CustomerAnalyticsSchema

    class Config:
        from_attributes = True