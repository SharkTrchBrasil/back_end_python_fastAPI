from src.api.admin.schemas.order import Order
from src.api.app.services.rating import get_product_ratings_summary, get_store_ratings_summary
from src.api.shared_schemas.rating import RatingsSummaryOut
from src.socketio_instance import sio
from src.core import models
from src.core.database import get_db_manager
from src.api.shared_schemas.store_theme import StoreThemeOut
from src.api.app.schemas.store_details import StoreDetails
from src.api.shared_schemas.product import ProductOut
from sqlalchemy.orm import joinedload

async def emit_store_full_updated(db, store_id: int, sid: str | None = None):
    store = db.query(models.Store).options(
        joinedload(models.Store.payment_methods),
        joinedload(models.Store.delivery_config),
        joinedload(models.Store.hours),
        joinedload(models.Store.cities).joinedload(models.StoreCity.neighborhoods),
    ).filter_by(id=store_id).first()

    if store is None:
        print(f"emit_store_full_updated: loja {store_id} não encontrada")
        return

    try:
        store_schema = StoreDetails.model_validate(store)
    except Exception as e:
        print(f"Erro ao validar Store com Pydantic StoreDetails para loja {store.id}: {e}")
        raise ConnectionRefusedError(f"Dados malformados: {e}")

    store_schema.ratingsSummary = RatingsSummaryOut(
        **get_store_ratings_summary(db, store_id=store.id)
    )

    payload = store_schema.model_dump()
    target = sid if sid else f"store_{store_id}"
    await sio.emit("store_full_updated", payload, to=target)



async def emit_orders_initial(db, store_id: int, sid: str | None = None):
    orders = (
        db.query(models.Order)
        .filter(models.Order.store_id == store_id)
        .order_by(models.Order.created_at.desc())
        .limit(20)
        .all()
    )

    payload = [Order.model_validate(order).model_dump() for order in orders]

    target = sid if sid else f"store_{store_id}"
    await sio.emit("orders_initial", payload, to=target)



async def emit_order_updated(db, order_id: int):
    order = db.query(models.Order).filter_by(id=order_id).first()
    if not order:
        return


    payload = Order.model_validate(order).model_dump()
    await sio.emit("order_updated", payload, to=f"store_{order.store_id}")





async def product_list_all(db, store_id: int, sid: str | None = None):
    products_list = db.query(models.Product).options(
        joinedload(models.Product.variant_links)
        .joinedload(models.ProductVariantProduct.variant)
        .joinedload(models.Variant.options)
    ).filter_by(store_id=store_id, available=True).all()

    # Pega avaliações dos produtos
    product_ratings = {
        product.id: get_product_ratings_summary(db, product_id=product.id)
        for product in products_list
    }

    # Junta dados do produto + avaliações
    payload = [
        {
            **ProductOut.from_orm_obj(product).model_dump(exclude_unset=True),
            "rating": product_ratings.get(product.id),
        }
        for product in products_list
    ]

    target = sid if sid else f"store_{store_id}"
    await sio.emit("products_updated", payload, to=target)




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
