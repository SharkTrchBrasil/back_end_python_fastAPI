from pydantic import BaseModel
from datetime import datetime

class BillingPreviewSchema(BaseModel):
    """Schema para o resumo e projeção de faturamento do ciclo atual."""
    period_start: datetime
    period_end: datetime
    revenue_so_far: float
    orders_so_far: int
    fee_so_far: float
    projected_revenue: float
    projected_fee: float