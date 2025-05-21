from fastapi import APIRouter, HTTPException

from src.api.admin.schemas.variant import VariantCreate, Variant, VariantUpdate
from src.core import models
from src.core.database import GetDBDep
from src.core.dependencies import GetProductDep, GetVariantDep, GetStoreDep

router = APIRouter(tags=["Variants"], prefix="/stores/{store_id}/variants")

@router.post("", response_model=Variant)
def create_product_variant(
        db: GetDBDep,
        store: GetStoreDep,
        variant: VariantCreate,
):
    db_variant = models.Variant(
        **variant.model_dump(),
        store_id=store.store_id,
    )

    db.add(db_variant)
    db.commit()
    return db_variant


@router.get("/{variant_id}", response_model=Variant)
def get_product_variant(
    variant: GetVariantDep
):
    return variant

@router.patch("/{variant_id}", response_model=Variant)
def patch_product_variant(
    db: GetDBDep,
    variant: GetVariantDep,
    variant_update: VariantUpdate,
):
    for field, value in variant_update.model_dump(exclude_unset=True).items():
        setattr(variant, field, value)

    db.commit()
    return variant