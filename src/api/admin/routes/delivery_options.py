from fastapi import APIRouter, Form, HTTPException
from src.api.admin.schemas.store_delivery_options import StoreDeliveryOption
from src.core import models
from src.core.database import GetDBDep
from src.core.dependencies import GetStoreDep

router = APIRouter(tags=["Delivery Options"], prefix="/stores/{store_id}/delivery-options")


@router.post("", response_model=StoreDeliveryOption)
def create_delivery_option(
    db: GetDBDep,
    store: GetStoreDep,
    mode: str = Form(...),
    title: str = Form(...),
    enabled: bool = Form(True),
    estimated_min: int | None = Form(None),
    estimated_max: int | None = Form(None),
    delivery_fee: float | None = Form(None),
    min_order_value: float | None = Form(None),
    instructions: str | None = Form(None),
):
    db_option = models.StoreDeliveryOption(
        store_id=store.id,
        mode=mode,
        title=title,
        enabled=enabled,
        estimated_min=estimated_min,
        estimated_max=estimated_max,
        delivery_fee=delivery_fee,
        min_order_value=min_order_value,
        instructions=instructions,
    )

    db.add(db_option)
    db.commit()
    db.refresh(db_option)

    return db_option


@router.get("", response_model=list[StoreDeliveryOption])
def get_delivery_options(
    db: GetDBDep,
    store: GetStoreDep,
):
    return db.query(models.StoreDeliveryOption).filter(models.StoreDeliveryOption.store_id == store.id).all()


@router.get("/{option_id}", response_model=StoreDeliveryOption)
def get_delivery_option(
    db: GetDBDep,
    store: GetStoreDep,
    option_id: int,
):
    db_option = db.query(models.StoreDeliveryOption).filter(
        models.StoreDeliveryOption.id == option_id,
        models.StoreDeliveryOption.store_id == store.id
    ).first()

    if not db_option:
        raise HTTPException(status_code=404, detail="Delivery option not found")

    return db_option


@router.patch("/{option_id}", response_model=StoreDeliveryOption)
def update_delivery_option(
    db: GetDBDep,
    store: GetStoreDep,
    option_id: int,
    mode: str | None = Form(None),
    title: str | None = Form(None),
    enabled: bool | None = Form(None),
    estimated_min: int | None = Form(None),
    estimated_max: int | None = Form(None),
    delivery_fee: float | None = Form(None),
    min_order_value: float | None = Form(None),
    instructions: str | None = Form(None),
):
    db_option = db.query(models.StoreDeliveryOption).filter(
        models.StoreDeliveryOption.id == option_id,
        models.StoreDeliveryOption.store_id == store.id
    ).first()

    if not db_option:
        raise HTTPException(status_code=404, detail="Delivery option not found")

    if mode is not None:
        db_option.mode = mode
    if title is not None:
        db_option.title = title
    if enabled is not None:
        db_option.enabled = enabled
    if estimated_min is not None:
        db_option.estimated_min = estimated_min
    if estimated_max is not None:
        db_option.estimated_max = estimated_max
    if delivery_fee is not None:
        db_option.delivery_fee = delivery_fee
    if min_order_value is not None:
        db_option.min_order_value = min_order_value
    if instructions is not None:
        db_option.instructions = instructions

    db.commit()
    db.refresh(db_option)

    return db_option
