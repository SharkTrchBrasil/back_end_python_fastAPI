import asyncio

from fastapi import APIRouter, Form, HTTPException

from src.api.app.events.socketio_emitters import emit_store_updated
from src.api.shared_schemas.store_delivery_options import StoreDeliveryConfig
from src.core import models
from src.core.database import GetDBDep
from src.core.dependencies import GetStoreDep

router = APIRouter(tags=["Delivery Config"], prefix="/stores/{store_id}/delivery-config")


@router.get("", response_model=StoreDeliveryConfig)
def get_delivery_config(
    db: GetDBDep,
    store: GetStoreDep,
):
    config = (
        db.query(models.StoreDeliveryConfiguration)
        .filter(models.StoreDeliveryConfiguration.store_id == store.id)
        .first()
    )

    if not config:
        raise HTTPException(status_code=404, detail="Delivery config not found")

    return config


@router.put("", response_model=StoreDeliveryConfig)
def update_delivery_config(
    db: GetDBDep,
    store: GetStoreDep,

    # DELIVERY
    delivery_enabled: bool = Form(...),
    delivery_estimated_min: int | None = Form(None),
    delivery_estimated_max: int | None = Form(None),
    delivery_fee: float | None = Form(None),
    delivery_min_order: float | None = Form(None),
    delivery_scope:  str | None = Form(None),

    # PICKUP
    pickup_enabled: bool = Form(...),
    pickup_estimated_min: int | None = Form(None),
    pickup_estimated_max: int | None = Form(None),
    pickup_instructions: str | None = Form(None),

    # TABLE
    table_enabled: bool = Form(...),
    table_estimated_min: int | None = Form(None),
    table_estimated_max: int | None = Form(None),
    table_instructions: str | None = Form(None),
):
    config = (
        db.query(models.StoreDeliveryConfiguration)
        .filter(models.StoreDeliveryConfiguration.store_id == store.id)
        .first()
    )

    if not config:
        config = models.StoreDeliveryConfiguration(store_id=store.id)
        db.add(config)

    config.delivery_enabled = delivery_enabled
    config.delivery_estimated_min = delivery_estimated_min
    config.delivery_estimated_max = delivery_estimated_max
    config.delivery_fee = delivery_fee
    config.delivery_min_order = delivery_min_order
    config.delivery_scope = delivery_scope

    config.pickup_enabled = pickup_enabled
    config.pickup_estimated_min = pickup_estimated_min
    config.pickup_estimated_max = pickup_estimated_max
    config.pickup_instructions = pickup_instructions

    config.table_enabled = table_enabled
    config.table_estimated_min = table_estimated_min
    config.table_estimated_max = table_estimated_max
    config.table_instructions = table_instructions

    db.commit()
    db.refresh(config)
    asyncio.create_task(emit_store_updated(store.id))

    return config
