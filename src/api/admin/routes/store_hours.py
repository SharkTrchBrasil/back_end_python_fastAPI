from fastapi import APIRouter, Form, HTTPException, File, UploadFile
from src.api.admin.schemas.store import StoreCreate, StoreWithRole, Roles
from src.api.admin.schemas.store_hours import StoreHours
from src.core.aws import upload_file, delete_file
from src.core.database import GetDBDep
from src.core.dependencies import GetStoreDep

router = APIRouter(prefix="/stores/{store_id}/hours", tags=["Hours"])

@router.post("", response_model=StoreHours)
def create_store_hour(
    db: GetDBDep,
    store: GetStoreDep,
    day_of_week: int = Form(...),      # 0-domingo a 6-sábado
    open_time: str = Form(...),        # formato 'HH:MM'
    close_time: str = Form(...),       # formato 'HH:MM'
    shift_number: int = Form(...),     # 1, 2, 3...
    is_active: bool = Form(...),       # true ou false
):
    db_store_hour = StoreHours(
        day_of_week=day_of_week,
        open_time=open_time,
        close_time=close_time,
        shift_number=shift_number,
        is_active=is_active,
        store_id=store.id,
    )

    db.add(db_store_hour)
    db.commit()
    return db_store_hour


@router.get("", response_model=list[StoreHours])
def get_store_hours(
    db: GetDBDep,
    store: GetStoreDep,
):
    db_store_hours = db.query(StoreHours).filter(StoreHours.store_id == store.id).all()
    return db_store_hours

@router.get("/{hour_id}", response_model=StoreHours)
def get_store_hour(
    db: GetDBDep,
    store: GetStoreDep,
    hour_id: int,
):
    db_store_hour = db.query(StoreHours).filter(StoreHours.id == hour_id, StoreHours.store_id == store.id).first()
    if not db_store_hour:
        raise HTTPException(status_code=404, detail="Store hour not found")
    return db_store_hour

@router.patch("/{hour_id}", response_model=StoreHours)
def patch_store_hour(
    db: GetDBDep,
    store: GetStoreDep,
    hour_id: int,
    day_of_week: int | None = Form(None),
    open_time: str | None = Form(None),
    close_time: str | None = Form(None),
    shift_number: int | None = Form(None),
    is_active: bool | None = Form(None),
):
    db_store_hour = db.query(StoreHours).filter(StoreHours.id == hour_id, StoreHours.store_id == store.id).first()
    if not db_store_hour:
        raise HTTPException(status_code=404, detail="Store hour not found")

    if day_of_week is not None:
        db_store_hour.day_of_week = day_of_week
    if open_time is not None:
        db_store_hour.open_time = open_time
    if close_time is not None:
        db_store_hour.close_time = close_time
    if shift_number is not None:
        db_store_hour.shift_number = shift_number
    if is_active is not None:
        db_store_hour.is_active = is_active

    db.commit()
    return db_store_hour
