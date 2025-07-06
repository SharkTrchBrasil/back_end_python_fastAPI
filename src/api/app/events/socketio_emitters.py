from src.api.app.services.rating import get_product_ratings_summary
from src.socketio_instance import sio
from src.core import models
from src.core.database import get_db_manager
from src.api.shared_schemas.store_theme import StoreThemeOut
from src.api.app.schemas.store_details import StoreDetails
from src.api.shared_schemas.product import ProductOut
from sqlalchemy.orm import joinedload


async def emit_store_updated(store: models.Store):
    await sio.emit(
        'store_updated',
        StoreDetails.model_validate(store).model_dump(),
        to=f'store_{store.id}'
    )

async def emit_theme_updated(theme: models.StoreTheme):
    # Converte ORM para Pydantic para emitir JSON correto
    pydantic_theme = StoreThemeOut.model_validate(theme).model_dump()
    await sio.emit(
        'theme_updated',
        pydantic_theme,
        to=f'store_{theme.store_id}'
    )

async def emit_products_updated(store_id: int):
    with get_db_manager() as db:
        products = db.query(models.Product).options(
            joinedload(models.Product.variant_links)
            .joinedload(models.ProductVariantProduct.variant)
            .joinedload(models.Variant.options)
        ).filter_by(store_id=store_id, available=True).all()

        payload = [ProductOut.from_orm_obj(p).model_dump(exclude_unset=True) for p in products]

    await sio.emit('products_updated', payload, to=f'store_{store_id}')


async def refresh_product_list(db, store_id: int, sid: str | None = None):
    products_l = db.query(models.Product).options(
        joinedload(models.Product.variant_links)
        .joinedload(models.ProductVariantProduct.variant)
        .joinedload(models.Variant.options)
    ).filter_by(store_id=store_id, available=True).all()

    # Pega avaliações dos produtos
    product_ratings = {
        product.id: get_product_ratings_summary(db, product_id=product.id)
        for product in products_l
    }

    # Junta dados do produto + avaliações
    payload = [
        {
            **ProductOut.from_orm_obj(product).model_dump(exclude_unset=True),
            "rating": product_ratings.get(product.id),
        }
        for product in products_l
    ]

    target = sid if sid else f"store_{store_id}"
    await sio.emit("products_updated", payload, to=target)
