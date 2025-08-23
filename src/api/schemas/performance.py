# src/api/schemas/performance.py
from pydantic import BaseModel, Field
from datetime import date
from typing import List, Optional


# --- SCHEMAS DE DADOS BÁSICOS (PARA GRÁFICOS, ETC) ---

class SalesByHourSchema(BaseModel):
    hour: int
    total_value: float = Field(..., alias="totalValue")

    class Config:
        populate_by_name = True


class PaymentMethodSummarySchema(BaseModel):
    method_name: str
    method_icon: Optional[str] = None
    total_value: float
    transaction_count: int


class TopSellingProductSchema(BaseModel):
    product_id: int
    product_name: str
    quantity_sold: int
    total_value: float


class OrderStatusCountSchema(BaseModel):
    concluidos: int
    cancelados: int
    pendentes: int


# --- SCHEMAS AVANÇADOS COM COMPARAÇÃO ---

class ComparativeMetricSchema(BaseModel):
    """Um schema para qualquer métrica que precise de comparação."""
    current: float
    previous: float
    change_percentage: float = Field(..., alias="percentageChange")

    class Config:
        populate_by_name = True


class DailySummarySchema(BaseModel):
    """Resumo com métricas comparativas."""
    completed_sales: ComparativeMetricSchema = Field(..., alias="completedSales")
    total_value: ComparativeMetricSchema = Field(..., alias="totalValue")
    average_ticket: ComparativeMetricSchema = Field(..., alias="averageTicket")

    class Config:
        populate_by_name = True


class CustomerAnalyticsSchema(BaseModel):
    """Dados de clientes com métricas comparativas."""
    new_customers: ComparativeMetricSchema = Field(..., alias="newCustomers")
    returning_customers: ComparativeMetricSchema = Field(..., alias="returningCustomers")

    class Config:
        populate_by_name = True


# --- O SCHEMA DE RESPOSTA PRINCIPAL E COMPLETO ---

class StorePerformanceSchema(BaseModel):
    query_date: date = Field(..., alias="queryDate")
    comparison_date: date = Field(..., alias="comparisonDate")
    summary: DailySummarySchema
    gross_profit: ComparativeMetricSchema = Field(..., alias="grossProfit")
    customer_analytics: CustomerAnalyticsSchema = Field(..., alias="customerAnalytics")
    sales_by_hour: List[SalesByHourSchema] = Field(..., alias="salesByHour")
    payment_methods: List[PaymentMethodSummarySchema] = Field(..., alias="paymentMethods")
    top_selling_products: List[TopSellingProductSchema] = Field(..., alias="topSellingProducts")
    order_status_counts: OrderStatusCountSchema = Field(..., alias="orderStatusCounts")

    class Config:
        from_attributes = True
        populate_by_name = True