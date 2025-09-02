# Em: src/api/admin/schemas/dashboard.py

from pydantic import BaseModel, Field
from typing import List, Literal
from datetime import date

from src.api.schemas.store.store_payable import PayableResponse


# ===================================================================
# KPIs (INDICADORES CHAVE)
# ===================================================================
class DashboardKpiSchema(BaseModel):
    total_revenue: float = Field(..., description="Faturamento total no período.")
    transaction_count: int = Field(..., description="Número total de pedidos no período.")
    average_ticket: float = Field(..., description="Valor médio por pedido.")
    new_customers: int = Field(..., description="Número de novos clientes no período.")

    # --- NOVOS CAMPOS ---
    total_cashback: float = Field(..., description="Soma total de cashback concedido.")
    total_spent: float = Field(..., description="Total gasto (pode ser igual a faturamento, dependendo da regra).")
    revenue_change_percentage: float = Field(...,
                                             description="Variação percentual do faturamento em relação ao período anterior.")
    revenue_is_up: bool = Field(..., description="True se o faturamento aumentou em relação ao período anterior.")
    retention_rate: float = Field(..., description="Percentual de clientes que fizeram mais de um pedido.")




    class Config:
        from_attributes = True


# ===================================================================
# DADOS PARA GRÁFICOS
# ===================================================================
class SalesDataPointSchema(BaseModel):
    period: date = Field(..., description="A data do ponto de dados para o gráfico.")
    revenue: float = Field(..., description="O faturamento total para aquele dia.")

    class Config:
        from_attributes = True


# ===================================================================
# ITENS DE LISTAS "TOP 5"
# ===================================================================
class TopItemSchema(BaseModel):
    name: str = Field(..., description="Nome do item (produto ou categoria).")
    count: int = Field(..., description="Contagem de vendas ou pedidos do item.")

    # --- MELHORIA ---
    revenue: float = Field(..., description="Faturamento total gerado pelo item.")

    class Config:
        from_attributes = True

class OrderTypeSummarySchema(BaseModel):
    order_type: str # Ex: "delivery", "pickup"
    count: int


# ===================================================================
# NOVOS SCHEMAS PARA OS WIDGETS
# ===================================================================
class PaymentMethodSummarySchema(BaseModel):
    method_name: str = Field(..., description="Nome do método de pagamento (ex: 'Cartão de Crédito').")
    total_amount: float = Field(..., description="Valor total transacionado com este método.")

    class Config:
        from_attributes = True


class UserCardSchema(BaseModel):
    card_last_four_digits: str
    card_type: str
    balance: float
    card_art_url: str

    class Config:
        from_attributes = True


class CurrencyBalanceSchema(BaseModel):
    currency_code: str
    amount: float
    flag_icon_url: str

    class Config:
        from_attributes = True

# Crie um schema para o ponto de dado mensal
class MonthlyDataPoint(BaseModel):
    month: str  # Ex: "Maio", "Jun"
    count: int
# ===================================================================
# SCHEMA PRINCIPAL DA RESPOSTA
# ===================================================================
class DashboardDataSchema(BaseModel):
    kpis: DashboardKpiSchema
    sales_over_time: List[SalesDataPointSchema]
    top_products: List[TopItemSchema]
    top_categories: List[TopItemSchema]
    payment_methods: List[PaymentMethodSummarySchema]

    # Nota: Os campos abaixo são mais relacionados a um "wallet" do usuário
    # do que a um resumo de vendas da loja. Incluí o schema, mas retornaremos
    # uma lista vazia por enquanto, sugerindo que sejam de outro endpoint.
    user_cards: List[UserCardSchema] = []
    currency_balances: List[CurrencyBalanceSchema] = []
    new_customers_over_time: list[MonthlyDataPoint] = []
    top_product_by_revenue: TopItemSchema | None = None  # ✅
    order_type_distribution: list[OrderTypeSummarySchema] = []  # ✅ NOV

    class Config:
        from_attributes = True




class HolidayInsightDetails(BaseModel):
    holiday_name: str
    holiday_date: date


class DashboardInsight(BaseModel):
    # Usamos Literal para que o frontend saiba exatamente que tipo de alerta é este
    insight_type: Literal["UPCOMING_HOLIDAY"]
    title: str
    message: str
    details: HolidayInsightDetails # O payload específico do insight



class DashboardMetrics(BaseModel):
    total_pending: int       # Valor total de contas pendentes
    total_overdue: int       # Valor total de contas vencidas
    total_paid_month: int    # Valor total pago no mês corrente
    pending_count: int       # Número de contas pendentes
    overdue_count: int       # Número de contas vencidas
    next_due_payables: list[PayableResponse] # Lista das próximas 3-5 contas a vencer