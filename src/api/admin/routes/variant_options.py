import asyncio

from fastapi import APIRouter

from src.api.app.routes.realtime import refresh_product_list
from src.api.shared_schemas.variant import VariantOption
from src.api.shared_schemas.variant_option import VariantOptionCreate, VariantOptionUpdate
from src.core import models
from src.core.database import GetDBDep
from src.core.dependencies import GetVariantDep, GetVariantOptionDep

router = APIRouter(tags=["Variant Options"],
                   prefix='/stores/{store_id}/variants/{variant_id}/options')

@router.post("", response_model=VariantOption)
async def create_product_variant_option(
        db: GetDBDep,
        variant: GetVariantDep,
        option: VariantOptionCreate,
):
    db_option = models.VariantOptions(
        **option.model_dump(),
        variant_id=variant.id,
        store_id=variant.store_id,
    )

    db.add(db_option)
    db.commit()

    await refresh_product_list(db, db_option.store_id)

    return db_option

@router.get("/{option_id}", response_model=VariantOption)
def get_product_variant_option(
    option: GetVariantOptionDep
):
    return option


@router.patch("/{option_id}", response_model=VariantOption)
async def patch_product_variant_option(
    db: GetDBDep,
    option: GetVariantOptionDep,
    variant_update: VariantOptionUpdate,
):
    for field, value in variant_update.model_dump(exclude_unset=True).items():
        setattr(option, field, value)

    db.commit()
    await refresh_product_list(db, option.store_id)
    return option