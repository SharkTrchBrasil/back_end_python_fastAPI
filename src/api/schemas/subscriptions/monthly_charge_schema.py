# schemas/monthly_charge_schema.py

from datetime import date, datetime
from decimal import Decimal
from pydantic import BaseModel, ConfigDict


class MonthlyChargeSchema(BaseModel):
    """Schema para cobranças mensais calculadas."""
    model_config = ConfigDict(from_attributes=True)

    id: int
    store_id: int
    subscription_id: int

    charge_date: date
    billing_period_start: date
    billing_period_end: date

    total_revenue: Decimal
    calculated_fee: Decimal

    status: str  # pending, paid, failed
    gateway_transaction_id: str | None

    created_at: datetime
    updated_at: datetime