from pydantic import BaseModel
from typing import Optional, List



class StoreDeliveryConfigBase(BaseModel):
    # DELIVERY
    delivery_enabled: Optional[bool] = False
    delivery_estimated_min: Optional[int] = None
    delivery_estimated_max: Optional[int] = None
    delivery_fee: Optional[float] = None
    delivery_min_order: Optional[float] = None
    delivery_scope: Optional[str] = None

    # PICKUP
    pickup_enabled: Optional[bool] = False
    pickup_estimated_min: Optional[int] = None
    pickup_estimated_max: Optional[int] = None
    pickup_instructions: Optional[str] = None

    # TABLE / COUNTER
    table_enabled: Optional[bool] = False
    table_estimated_min: Optional[int] = None
    table_estimated_max: Optional[int] = None
    table_instructions: Optional[str] = None


    model_config = {
        "from_attributes": True,
        "arbitrary_types_allowed": True # ADICIONE ESTA LINHA AQUI
    }


class StoreDeliveryConfigCreate(StoreDeliveryConfigBase):
    pass

class StoreDeliveryConfigUpdate(StoreDeliveryConfigBase):
    pass

class StoreDeliveryConfig(StoreDeliveryConfigBase):
    id: int
    store_id: int



