from fastapi import APIRouter, HTTPException
from sqlalchemy.orm import joinedload

from src.api.admin.schemas.coupon import CouponCreate, Coupon, CouponUpdate
from src.core import models
from src.core.database import GetDBDep
from src.core.dependencies import GetStoreDep

router = APIRouter(tags=["Coupons"], prefix="/stores/{store_id}/coupons")

@router.post("", response_model=Coupon)
def create_coupon(
        db: GetDBDep,
        store: GetStoreDep,
        coupon: CouponCreate,
):
    existing_coupon = db.query(models.Coupon).filter(
        models.Coupon.code == coupon.code,
        models.Coupon.store_id == store.id,
    ).first()

    if existing_coupon:
        raise HTTPException(status_code=400, detail={
            "code": "CODE_ALREADY_EXISTS",
            "message": "A coupon with this code already exists for this store."
        })

    db_coupon = models.Coupon(
        **coupon.model_dump(),
        store_id=store.id,
    )

    db.add(db_coupon)
    db.commit()
    return db_coupon



@router.get("", response_model=list[Coupon])
def get_coupons(
        db: GetDBDep,
        store: GetStoreDep,
):
    coupons = db.query(models.Coupon).filter(
        models.Coupon.store_id == store.id,
    ).all()

    return coupons


# # alterado do original para buscar o produto vinculado
# @router.get("", response_model=list[Coupon])
# def get_coupons(
#         db: GetDBDep,
#         store: GetStoreDep,
# ):
#     coupons = db.query(models.Coupon).filter(
#         models.Coupon.store_id == store.id,
#     ).options(
#         joinedload(models.Coupon.product) # Carrega o produto e, dentro dele, a imagem
#     ).all()
#
#     return coupons

@router.get("/{coupon_id}", response_model=Coupon)
def get_coupon(
        db: GetDBDep,
        store: GetStoreDep,
        coupon_id: int
):
    coupon = db.query(models.Coupon).filter(
        models.Coupon.id == coupon_id,
        models.Coupon.store_id == store.id,
    ).first()

    if not coupon:
        raise HTTPException(status_code=404, detail="Coupon not found")

    return coupon


@router.patch("/{coupon_id}", response_model=Coupon)
def patch_coupon(
    db: GetDBDep,
    store: GetStoreDep,
    coupon_id: int,
    coupon_update: CouponUpdate,
):
    coupon = db.query(models.Coupon).filter(
        models.Coupon.id == coupon_id,
        models.Coupon.store_id == store.id,
    ).first()

    if not coupon:
        raise HTTPException(status_code=404, detail="Coupon not found")

    for field, value in coupon_update.model_dump(exclude_unset=True).items():
        setattr(coupon, field, value)

    db.commit()
    return coupon