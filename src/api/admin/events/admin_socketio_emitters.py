from src.api.admin.schemas.order import Order
from src.socketio_instance import sio
from src.core import models
from src.core.database import get_db_manager
from src.api.shared_schemas.store_theme import StoreThemeOut
from src.api.app.schemas.store_details import StoreDetails
from src.api.shared_schemas.product import ProductOut
from sqlalchemy.orm import joinedload




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
