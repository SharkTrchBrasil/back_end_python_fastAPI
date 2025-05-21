from fastapi import APIRouter, HTTPException

from src.api.admin.schemas.product_variant_option import VariantOption, VariantOptionCreate, \
    VariantOptionUpdate
from src.core import models
from src.core.database import GetDBDep
from src.core.dependencies import GetVariantDep, GetVariantOptionDep
from src.core.models import VariantOption

router = APIRouter(tags=["Variant Options"],
                   prefix='/stores/{store_id}/variants/{variant_id}/options')

@router.post("", response_model=VariantOption)
def create_product_variant_option(
        db: GetDBDep,
        variant: GetVariantDep,
        option: VariantOptionCreate,
):
    db_option = models.VariantOption(
        **option.model_dump(),
        variant_id=variant.id,
    )

    db.add(db_option)
    db.commit()
    return db_option

@router.get("/{option_id}", response_model=VariantOption)
def get_product_variant_option(
    option: GetVariantOptionDep
):
    return option


@router.patch("/{option_id}", response_model=VariantOption)
def patch_product_variant_option(
    db: GetDBDep,
    option: GetVariantOptionDep,
    variant_update: VariantOptionUpdate,
):
    for field, value in variant_update.model_dump(exclude_unset=True).items():
        setattr(option, field, value)

    db.commit()
    return option