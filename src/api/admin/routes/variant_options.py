from fastapi import APIRouter

from src.api.app.socketio.socketio_emitters import emit_products_updated
from src.api.schemas import VariantOption
from src.api.schemas.variant import VariantOptionCreate, VariantOptionUpdate

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
    db_option = models.VariantOption(
        **option.model_dump(),

        store_id=variant.store_id, # usado para fazer refres no socket.io
    )

    db.add(db_option)
    db.commit()

    await emit_products_updated(db, db_option.store_id)

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
    await emit_products_updated(db, option.store_id)
    return option



@router.delete("/{option_id}", status_code=204)
async def delete_product_variant_option(
    db: GetDBDep,
    option: GetVariantOptionDep,
):
    store_id = option.store_id  # salva para usar no refresh depois

    db.delete(option)
    db.commit()

    await emit_products_updated(db, store_id)

    return None  # status_code 204 (No Content) não precisa retornar nada

