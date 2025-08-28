# schemas/order/order_print_log.py
from pydantic import ConfigDict

from ..base_schema import AppBaseModel


class OrderPrintLogSchema(AppBaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    printer_destination: str
    status: str