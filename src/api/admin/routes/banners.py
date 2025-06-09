from datetime import datetime
from typing import Optional

from fastapi import APIRouter, HTTPException, UploadFile, File, Form
from sqlalchemy.orm import joinedload

from src.api.shared_schemas.banner import BannerOut
from src.api.shared_schemas.coupon import CouponCreate, Coupon, CouponUpdate
from src.core import models
from src.core.aws import upload_file, delete_file
from src.core.database import GetDBDep
from src.core.dependencies import GetStoreDep

router = APIRouter(tags=["Banners"], prefix="/stores/{store_id}/banners")

@router.post("", response_model=BannerOut)
async def create_banner(
    db: GetDBDep,
    store: GetStoreDep,
    image: UploadFile = File(...),  # este é o arquivo vindo do Flutter como "file"
    product_id: int | None = Form(None),
    category_id: int | None = Form(None),
    is_active: bool = Form(True),
    position: int | None = Form(None),
    link_url: Optional[str] = Form(None),
    start_date: datetime = Form(...),
    end_date: datetime = Form(...)
):
    file_key = upload_file(image)  # usa o mesmo nome do parâmetro

    banner = models.Banner(
        store_id=store.id,
        file_key=file_key,
        product_id=product_id,
        category_id=category_id,
        is_active=is_active,
        position=position,
        link_url=link_url,
        start_date=start_date,
        end_date=end_date,
    )

    db.add(banner)
    db.commit()
    db.refresh(banner)

    return banner




@router.get("", response_model=list[BannerOut])
def get_banners(
    db: GetDBDep,
    store: GetStoreDep,
):
    banners = db.query(models.Banner).filter(
        models.Banner.store_id == store.id
    ).all()

    return banners



@router.get("/{banner_id}", response_model=BannerOut)
def get_banner(
    banner_id: int,
    db: GetDBDep,
    store: GetStoreDep,
):
    banner = db.query(models.Banner).filter(
        models.Banner.id == banner_id,
        models.Banner.store_id == store.id
    ).first()

    if not banner:
        raise HTTPException(status_code=404, detail="Banner not found")

    return banner

@router.patch("/{banner_id}", response_model=BannerOut)
async def update_banner(
    banner_id: int,
    db: GetDBDep,
    store: GetStoreDep,
    image: UploadFile | None = File(None),  # aqui trocamos "image" por "file"
    product_id: int | None = Form(None),
    category_id: int | None = Form(None),
    is_active: bool | None = Form(None),
    position: int | None = Form(None),
    link_url: str | None = Form(None),
    start_date: datetime | None = Form(None),
    end_date: datetime | None = Form(None),
):
    banner = db.query(models.Banner).filter(
        models.Banner.id == banner_id,
        models.Banner.store_id == store.id
    ).first()

    if not banner:
        raise HTTPException(status_code=404, detail="Banner not found")

    old_file_key = None

    if product_id is not None:
        banner.product_id = product_id
    if category_id is not None:
        banner.category_id = category_id
    if is_active is not None:
        banner.is_active = is_active
    if position is not None:
        banner.position = position
    if link_url is not None:
        banner.link_url = link_url
    if start_date is not None:
        banner.start_date = start_date
    if end_date is not None:
        banner.end_date = end_date
    if image:
        old_file_key = banner.file_key
        banner.file_key = upload_file(image)

    db.commit()
    db.refresh(banner)

    if old_file_key:
        delete_file(old_file_key)

    return banner



@router.delete("/{banner_id}", status_code=204)
async def delete_banner(
    banner_id: int,
    db: GetDBDep,
    store: GetStoreDep,
):
    banner = db.query(models.Banner).filter(
        models.Banner.id == banner_id,
        models.Banner.store_id == store.id
    ).first()

    if not banner:
        raise HTTPException(status_code=404, detail="Banner not found")

    if banner.file_key:
        delete_file(banner.file_key)

    db.delete(banner)
    db.commit()


