from fastapi import APIRouter, HTTPException

from src.api.admin.schemas.product_variant_option import ProductVariantOption, ProductVariantOptionCreate, \
    ProductVariantOptionUpdate
from src.core import models
from src.core.database import GetDBDep
from src.core.dependencies import GetVariantDep, GetVariantOptionDep

router = APIRouter(tags=["Variant Options"],
                   prefix='/stores/{store_id}/variants/{variant_id}/options')

@router.post("", response_model=ProductVariantOption)
def create_product_variant_option(
        db: GetDBDep,
        variant: GetVariantDep,
        option: ProductVariantOptionCreate,
):
    db_option = models.ProductVariantOption(
        **option.model_dump(),

        store_id=variant.store_id,
        product_variant_id=variant.id,
    )

    db.add(db_option)
    db.commit()
    return db_option

@router.get("/{option_id}", response_model=ProductVariantOption)
def get_product_variant_option(
    option: GetVariantOptionDep
):
    return option


@router.patch("/{option_id}", response_model=ProductVariantOption)
def patch_product_variant_option(
    db: GetDBDep,
    option: GetVariantOptionDep,
    variant_update: ProductVariantOptionUpdate,
):
    for field, value in variant_update.model_dump(exclude_unset=True).items():
        setattr(option, field, value)

    db.commit()
    return option