# Em: src/api/admin/schemas/dashboard.py (ou onde preferir)

from pydantic import BaseModel, Field
from typing import List
from datetime import date

# Schema para os cartões de KPIs (Indicadores-Chave)
class DashboardKpiSchema(BaseModel):
    total_revenue: float = Field(..., description="Faturamento total no período selecionado.")
    total_orders: int = Field(..., description="Número total de pedidos no período.")
    average_ticket: float = Field(..., description="Valor médio por pedido (ticket médio).")
    new_customers: int = Field(..., description="Número de clientes que fizeram o primeiro pedido no período.")

    class Config:
        orm_mode = True # ou from_attributes = True para Pydantic V2

# Schema para cada ponto de dados no gráfico de vendas
class SalesDataPointSchema(BaseModel):
    # Usamos 'date' para agrupar por dia, mas poderia ser 'hour' ou 'month'
    period: str = Field(..., description="O período do dado (ex: '2025-08-07' ou '14h').")
    revenue: float = Field(..., description="O faturamento total para aquele período.")

    class Config:
        orm_mode = True

# Schema para os itens nas listas de "Top 5"
class TopItemSchema(BaseModel):
    name: str = Field(..., description="Nome do item (produto ou categoria).")
    count: int = Field(..., description="Contagem de vendas ou pedidos do item.")
    # Opcional: você pode adicionar o faturamento por item também
    # revenue: float

    class Config:
        orm_mode = True

# Schema principal que junta tudo em uma única resposta da API
class DashboardDataSchema(BaseModel):
    kpis: DashboardKpiSchema
    sales_over_time: List[SalesDataPointSchema]
    top_products: List[TopItemSchema]
    top_categories: List[TopItemSchema]

    class Config:
        orm_mode = True