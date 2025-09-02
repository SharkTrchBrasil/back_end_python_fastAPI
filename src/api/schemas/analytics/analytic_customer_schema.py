# Crie este novo arquivo: src/api/admin/schemas/analytic_customer_schema.py

from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import date

# ===================================================================
# MODELOS DE DADOS
# ===================================================================

class CustomerMetric(BaseModel):
    """
    Representa os dados calculados para um único cliente.
    """
    customer_id: int
    name: str
    total_spent: float = Field(..., description="Valor total gasto pelo cliente na loja")
    order_count: int = Field(..., description="Número total de pedidos feitos pelo cliente")
    last_order_date: date = Field(..., description="Data do último pedido do cliente")

class KeyCustomerMetrics(BaseModel):
    """
    Agrupa os KPIs (indicadores chave) de alto nível sobre os clientes.
    """
    new_customers: int = Field(..., description="Número de clientes que fizeram a primeira compra no período")
    returning_customers: int = Field(..., description="Número de clientes que já compravam antes e voltaram no período")
    retention_rate: float = Field(..., description="Taxa de retenção de clientes em porcentagem (0 a 100)")

class RfmSegment(BaseModel):
    """
    Representa um segmento de clientes (ex: Campeões) e a lista de clientes nele.
    """
    segment_name: str
    description: str = Field(..., description="Uma breve explicação sobre o que o segmento significa")
    suggestion: str = Field(..., description="Uma sugestão de ação de marketing para este segmento")
    customers: List[CustomerMetric]

# ===================================================================
# MODELO PRINCIPAL DA RESPOSTA DA API
# ===================================================================

class CustomerAnalyticsResponse(BaseModel):
    """
    A resposta completa da API com toda a análise de clientes.
    """
    key_metrics: KeyCustomerMetrics
    segments: List[RfmSegment]