import asyncio

from fastapi import APIRouter, HTTPException
from sqlalchemy.orm import joinedload

from src.api.app.routes.realtime import refresh_product_list
from src.api.shared_schemas.variant import VariantCreate, Variant, VariantUpdate
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
        store_id=store.id,
    )

    db.add(db_variant)
    db.commit()
    asyncio.create_task(refresh_product_list(db, store.id))
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
    store: GetStoreDep,
    variant_update: VariantUpdate,
):
    for field, value in variant_update.model_dump(exclude_unset=True).items():
        setattr(variant, field, value)

    db.commit()
    asyncio.create_task(refresh_product_list(db, store.id))
    return variant



@router.get("", response_model=list[Variant])
def list_variants(store_id: int, db: GetDBDep, store: GetStoreDep):
    variants = (
        db.query(models.Variant)
        .options(joinedload(models.Variant.options))  # <-- carrega as opções junto
        .filter(models.Variant.store_id == store.id)
        .all()
    )
    return variants


@router.delete("/{variant_id}", status_code=204)
def delete_product_variant(
    db: GetDBDep,
    store: GetStoreDep,
    variant: GetVariantDep,
):
    db.delete(variant)
    db.commit()
    asyncio.create_task(refresh_product_list(db, store.id))
