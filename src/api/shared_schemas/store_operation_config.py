# Em um novo arquivo, ex: schemas/store_configuration.py

from pydantic import BaseModel
from typing import Optional


class StoreOperationConfigBase(BaseModel):
    # Campos que eram do StoreSettings
    is_store_open: bool = True
    auto_accept_orders: bool = False
    auto_print_orders: bool = False
    main_printer_destination: Optional[str] = None
    kitchen_printer_destination: Optional[str] = None
    bar_printer_destination: Optional[str] = None

    # Campos que eram do DeliveryOptions (e unificados)
    delivery_enabled: bool = False  # Unifica isDeliveryActive e deliveryEnabled
    delivery_estimated_min: Optional[int] = None
    delivery_estimated_max: Optional[int] = None
    delivery_fee: Optional[float] = None
    delivery_min_order: Optional[float] = None
    delivery_scope: Optional[str] = "neighborhood"

    pickup_enabled: bool = False  # Unifica isTakeoutActive e pickupEnabled
    pickup_estimated_min: Optional[int] = None
    pickup_estimated_max: Optional[int] = None
    pickup_instructions: Optional[str] = None

    table_enabled: bool = False  # Unifica isTableServiceActive e tableEnabled
    table_estimated_min: Optional[int] = None
    table_estimated_max: Optional[int] = None
    table_instructions: Optional[str] = None

    model_config = {"from_attributes": True}


class StoreOperationConfigOut(StoreOperationConfigBase):
    id: int
    store_id: int