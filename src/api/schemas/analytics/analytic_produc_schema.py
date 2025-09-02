# Em analytics/schemas.py

from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import date  # Usaremos date para facilitar comparações


# ===================================================================
# MODELOS DE ITEM INDIVIDUAL
# ===================================================================

class TopProductItem(BaseModel):
    product_id: int
    name: str
    image_url: Optional[str] = None
    revenue: float = Field(..., description="Faturamento total gerado pelo produto no período")
    units_sold: int = Field(..., description="Quantidade de unidades vendidas no período")
    profit: float = Field(..., description="Lucro total gerado pelo produto no período")

class LowTurnoverItem(BaseModel):
    product_id: int
    name: str
    image_url: Optional[str] = None
    stock_quantity: int = Field(..., description="Quantidade atual em estoque")
    days_since_last_sale: int = Field(..., description="Número de dias desde a última venda")
    profit: float = Field(..., description="Lucro potencial parado no estoque")


class AbcItem(BaseModel):
    product_id: int
    name: str
    revenue: float
    contribution_percentage: float = Field(..., description="Percentual de contribuição para o faturamento total")
    profit: float

# ===================================================================
# MODELOS DE SEÇÃO (AGRUPADORES)
# ===================================================================

class AbcAnalysis(BaseModel):
    class_a_items: List[AbcItem]
    class_b_items: List[AbcItem]
    class_c_items: List[AbcItem]


# ===================================================================
# MODELO PRINCIPAL DA RESPOSTA DA API
# ===================================================================


# ✅ NOVO MODELO PARA ESTOQUE BAIXO
class LowStockItem(BaseModel):
    product_id: int
    name: str
    image_url: Optional[str] = None
    stock_quantity: int
    minimum_stock_level: int # Importante para dar contexto




class ProductAnalyticsResponse(BaseModel):
    top_products: List[TopProductItem]
    low_turnover_items: List[LowTurnoverItem]
    abc_analysis: AbcAnalysis
    low_stock_items: List[LowStockItem]  # ✅ ADICIONADO AQUI


