from datetime import datetime
from venv import logger
from zoneinfo import ZoneInfo


from src.api.admin.schemas.store_settings import StoreSettingsBase

from src.api.app.services.rating import get_product_ratings_summary, get_store_ratings_summary
from src.api.shared_schemas.order import OrderDetails
from src.api.shared_schemas.rating import RatingsSummaryOut
from src.socketio_instance import sio
from src.core import models
from src.api.shared_schemas.store_theme import StoreThemeOut
from src.api.shared_schemas.store_details import StoreDetails
from src.api.shared_schemas.product import ProductOut
from sqlalchemy.orm import joinedload
from sqlalchemy.orm import selectinload

import orjson

async def admin_emit_store_full_updated(db, store_id: int, sid: str | None = None):
    print(f"🔄 [Admin] emit_store_full_updated para store_id: {store_id}")

    try:
        store = db.query(models.Store).options(
            joinedload(models.Store.payment_methods),
            joinedload(models.Store.delivery_config),
            joinedload(models.Store.hours),
            joinedload(models.Store.cities).joinedload(models.StoreCity.neighborhoods),
        ).filter_by(id=store_id).first()

        if not store:
            print(f"❌ Loja {store_id} não encontrada")
            return

        settings = db.query(models.StoreSettings).filter_by(store_id=store_id).first()
        if not settings:
            settings = models.StoreSettings(
                store_id=store_id,
                is_delivery_active=False,
                is_takeout_active=True,
                is_table_service_active=False,
                is_store_open=False,
                auto_accept_orders=False,
                auto_print_orders=False
            )
            db.add(settings)
            db.commit()
            print(f"⚙️ Configurações padrão criadas para loja {store_id}")

        store_schema = StoreDetails.model_validate(store)

        try:
            store_schema.ratingsSummary = RatingsSummaryOut(
                **get_store_ratings_summary(db, store_id=store.id)
            )
        except Exception:
            store_schema.ratingsSummary = RatingsSummaryOut(
                average_rating=0,
                total_ratings=0,
                distribution={1: 0, 2: 0, 3: 0, 4: 0, 5: 0},
                ratings=[]
            )

        payload = {
            "store_id": store_id,
            "store": store_schema.model_dump(),
        }
        payload['store']['store_settings'] = StoreSettingsBase.model_validate(settings).model_dump(mode='json')

        if sid:
            await sio.emit("store_full_updated", payload, namespace='/admin', to=sid)
        else:
            await sio.emit("store_full_updated", payload, namespace='/admin', room=f"admin_store_{store_id}")

    except Exception as e:
        print(f'❌ Erro crítico em emit_store_full_updated: {str(e)}')
        if sid:
            await sio.emit("store_full_updated", {"store_id": store_id, "store": {}}, namespace='/admin', to=sid)
        else:
            await sio.emit("store_full_updated", {"store_id": store_id, "store": {}}, namespace='/admin', room=f"admin_store_{store_id}")



async def admin_emit_orders_initial(db, store_id: int, sid: str | None = None):
    print(f"🔄 [Admin] emit_orders_initial para store_id: {store_id}")

    try:
        now = datetime.now(ZoneInfo("America/Sao_Paulo"))
        start_of_day = now.replace(hour=0, minute=0, second=0, microsecond=0)
        end_of_day = now.replace(hour=23, minute=59, second=59, microsecond=999999)

        orders = (
            db.query(models.Order)
            .options(
                selectinload(models.Order.products)
                .selectinload(models.OrderProduct.variants)
                .selectinload(models.OrderVariant.options)
            )
            .filter(
                models.Order.store_id == store_id,
                models.Order.created_at >= start_of_day,
                models.Order.created_at <= end_of_day,
            )
            .all()
        )

        orders_data = [
            OrderDetails.model_validate(order).model_dump(mode='json')
            for order in orders
        ]

        payload = {
            "store_id": store_id,
            "orders": orders_data
        }

        if sid:
            await sio.emit("orders_initial", payload, namespace='/admin', to=sid)
        else:
            await sio.emit("orders_initial", payload, namespace='/admin', room=f"admin_store_{store_id}")

    except Exception as e:
        print(f'❌ Erro em emit_orders_initial: {str(e)}')
        if sid:
            await sio.emit("orders_initial", {"store_id": store_id, "orders": []}, namespace='/admin', to=sid)
        else:
            await sio.emit("orders_initial", {"store_id": store_id, "orders": []}, namespace='/admin', room=f"admin_store_{store_id}")



async def admin_product_list_all(db, store_id: int, sid: str | None = None):
    print(f"🔄 [Admin] product_list_all para store_id: {store_id}")

    try:
        products = db.query(models.Product).options(
            joinedload(models.Product.variant_links)
            .joinedload(models.ProductVariantProduct.variant)
            .joinedload(models.Variant.options)
        ).filter_by(store_id=store_id, available=True).all()

        products_data = []
        if products:
            product_ratings = {
                product.id: get_product_ratings_summary(db, product_id=product.id)
                for product in products
            }

            products_data = [
                {
                    **ProductOut.from_orm_obj(product).model_dump(exclude_unset=True),
                    "rating": product_ratings.get(product.id) or {
                        "average_rating": 0,
                        "total_ratings": 0,
                        "distribution": {1: 0, 2: 0, 3: 0, 4: 0, 5: 0}
                    },
                }
                for product in products
            ]

        payload = {
            "store_id": store_id,
            "products": products_data
        }

        if sid:
            await sio.emit("products_updated", payload, namespace='/admin', to=sid)
        else:
            await sio.emit("products_updated", payload, namespace='/admin', room=f"admin_store_{store_id}")

    except Exception as e:
        print(f'❌ Erro em product_list_all: {str(e)}')
        if sid:
            await sio.emit("products_updated", {"store_id": store_id, "products": []}, namespace='/admin', to=sid)
        else:
            await sio.emit("products_updated", {"store_id": store_id, "products": []}, namespace='/admin', room=f"admin_store_{store_id}")


async def admin_emit_order_updated_from_obj(order: models.Order):
    try:
        order_data = OrderDetails.model_validate(order).model_dump(mode='json')
        await sio.emit("order_updated", order_data, namespace='/admin', room=f"admin_store_{order.store_id}")
    except Exception as e:
        logger.error(f'Erro ao emitir order_updated: {e}')

async def admin_emit_store_updated(store: models.Store):
    try:
        await sio.emit(
            'store_updated',
            StoreDetails.model_validate(store).model_dump(),
            namespace='/admin',
            room=f'admin_store_{store.id}'
        )
    except Exception as e:
        print(f'❌ Erro ao emitir store_updated: {str(e)}')


async def admin_emit_theme_updated(theme: models.StoreTheme):
    try:
        pydantic_theme = StoreThemeOut.model_validate(theme).model_dump()
        await sio.emit(
            'theme_updated',
            pydantic_theme,
            namespace='/admin',
            room=f'admin_store_{theme.store_id}'
        )
    except Exception as e:
        print(f'❌ Erro ao emitir theme_updated: {str(e)}')
