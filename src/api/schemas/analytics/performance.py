# src/api/schemas/performance.py
from pydantic import BaseModel, Field
from datetime import date
from typing import List, Optional

class TopAddonSchema(BaseModel):
    """Schema para os complementos (variant options) mais vendidos."""
    addon_name: str
    quantity_sold: int
    total_value: float

class CouponPerformanceSchema(BaseModel):
    """Schema para o desempenho de cada cupom usado no dia."""
    coupon_code: str
    times_used: int
    total_discount: float  # Soma dos descontos concedidos
    revenue_generated: float # Soma dos valores dos pedidos que usaram o cupom


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

class CategoryPerformanceSchema(BaseModel):
    category_id: int
    category_name: str
    total_value: float  # Faturamento gerado pela categoria
    gross_profit: float # Lucro bruto gerado pela categoria
    items_sold: int     # Quantidade de itens vendidos da categoria

class ProductFunnelSchema(BaseModel):
    product_id: int
    product_name: str
    view_count: int          # Total de visualizações
    sales_count: int         # Total de vezes que o item apareceu em pedidos
    quantity_sold: int       # Total de unidades vendidas
    conversion_rate: float   # (sales_count / view_count) * 100

# --- O SCHEMA DE RESPOSTA PRINCIPAL E COMPLETO ---

class TodaySummarySchema(BaseModel):
    """Schema simples para os dados de vendas do dia."""
    completed_sales: int
    total_value: float
    average_ticket: float


class DailyTrendPointSchema(BaseModel):
    """Representa os totais para um único dia no gráfico."""
    date: date
    sales_count: int
    total_value: float
    average_ticket: float
    new_customers: int

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

    top_selling_addons: List[TopAddonSchema] = Field(..., alias="topSellingAddons")
    coupon_performance: List[CouponPerformanceSchema] = Field(..., alias="couponPerformance")
    # ✅ NOVO CAMPO DO NÍVEL 3
    category_performance: List[CategoryPerformanceSchema] = Field(..., alias="categoryPerformance")

    # ✅ NOVO CAMPO DO FUNIL DE VENDAS
    product_funnel: List[ProductFunnelSchema] = Field(..., alias="productFunnel")
    # ✅ NOVO CAMPO PARA O GRÁFICO
    daily_trend: List[DailyTrendPointSchema] = Field(..., alias="dailyTrend")

    class Config:
        from_attributes = True
        populate_by_name = True