# schemas/store/store_operation_config.py
from typing import Optional
from pydantic import ConfigDict
from ..base_schema import AppBaseModel


class StoreOperationConfigBase(AppBaseModel):
    is_store_open: bool = True
    auto_accept_orders: bool = False
    auto_print_orders: bool = False
    main_printer_destination: Optional[str] = None
    kitchen_printer_destination: Optional[str] = None
    bar_printer_destination: Optional[str] = None
    delivery_enabled: bool = False
    delivery_estimated_min: Optional[int] = None
    delivery_estimated_max: Optional[int] = None
    delivery_fee: Optional[float] = None
    delivery_min_order: Optional[float] = None
    delivery_scope: Optional[str] = "neighborhood"
    pickup_enabled: bool = False
    pickup_estimated_min: Optional[int] = None
    pickup_estimated_max: Optional[int] = None
    pickup_instructions: Optional[str] = None
    table_enabled: bool = False
    table_estimated_min: Optional[int] = None
    table_estimated_max: Optional[int] = None
    table_instructions: Optional[str] = None
    free_delivery_threshold: Optional[float] = None

    model_config = ConfigDict(from_attributes=True)


class StoreOperationConfigOut(StoreOperationConfigBase):
    id: int
    store_id: int
    is_operational: bool = True