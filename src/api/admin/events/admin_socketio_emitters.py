from datetime import datetime

from src.api.admin.schemas.order import OrderDetails
from src.api.admin.schemas.store_settings import StoreSettingsBase

from src.api.app.services.rating import get_product_ratings_summary, get_store_ratings_summary
from src.api.shared_schemas.rating import RatingsSummaryOut
from src.socketio_instance import sio
from src.core import models
from src.api.shared_schemas.store_theme import StoreThemeOut
from src.api.shared_schemas.store_details import StoreDetails
from src.api.shared_schemas.product import ProductOut
from sqlalchemy.orm import joinedload
from sqlalchemy.orm import selectinload


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

        # Configurações padrão se não existirem
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

        # Ratings padrão se não existirem
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

        payload = store_schema.model_dump()
        payload['store_settings'] = StoreSettingsBase.model_validate(settings).model_dump(mode='json')

        target = sid if sid else f"admin_store_{store_id}"
        await sio.emit("store_full_updated", payload, namespace='/admin', to=target)

    except Exception as e:
        print(f'❌ Erro crítico em emit_store_full_updated: {str(e)}')
        raise


async def admin_emit_orders_initial(db, store_id: int, sid: str | None = None):
    print(f"🔄 [Admin] emit_orders_initial para store_id: {store_id}")

    try:
        now = datetime.utcnow()
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

        # Sempre retorna uma lista, mesmo que vazia
        payload = [
            OrderDetails.model_validate(order).model_dump(mode='json')
            for order in orders
        ] if orders else []

        target = sid if sid else f"admin_store_{store_id}"
        await sio.emit("orders_initial", payload, namespace='/admin', to=target)

    except Exception as e:
        print(f'❌ Erro em emit_orders_initial: {str(e)}')
        # Envia lista vazia em caso de erro
        target = sid if sid else f"admin_store_{store_id}"
        await sio.emit("orders_initial", [], namespace='/admin', to=target)


async def admin_product_list_all(db, store_id: int, sid: str | None = None):
    print(f"🔄 [Admin] product_list_all para store_id: {store_id}")

    try:
        products = db.query(models.Product).options(
            joinedload(models.Product.variant_links)
            .joinedload(models.ProductVariantProduct.variant)
            .joinedload(models.Variant.options)
        ).filter_by(store_id=store_id, available=True).all()

        # Cria payload com produtos ou lista vazia
        payload = []
        if products:
            product_ratings = {
                product.id: get_product_ratings_summary(db, product_id=product.id)
                for product in products
            }

            payload = [
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

        target = sid if sid else f"admin_store_{store_id}"
        await sio.emit("products_updated", payload, namespace='/admin', to=target)

    except Exception as e:
        print(f'❌ Erro em product_list_all: {str(e)}')
        # Envia lista vazia em caso de erro
        target = sid if sid else f"admin_store_{store_id}"
        await sio.emit("products_updated", [], namespace='/admin', to=target)


# As outras funções permanecem inalteradas
async def admin_emit_order_updated_from_obj(order: models.Order):
    try:
        payload = OrderDetails.model_validate(order).model_dump(mode='json')
        await sio.emit("order_updated", payload, namespace='/admin', to=f"admin_store_{order.store_id}")
    except Exception as e:
        print(f'❌ Erro ao emitir order_updated: {str(e)}')


async def admin_emit_store_updated(store: models.Store):
    try:
        await sio.emit(
            'store_updated',
            StoreDetails.model_validate(store).model_dump(),
            namespace='/admin',
            to=f'admin_store_{store.id}'
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
            to=f'admin_store_{theme.store_id}'
        )
    except Exception as e:
        print(f'❌ Erro ao emitir theme_updated: {str(e)}')































# async def admin_emit_store_full_updated(db, store_id: int, sid: str | None = None):
#     print(f"🔄 [Admin] emit_store_full_updated para store_id: {store_id}")
#
#     store = db.query(models.Store).options(
#         joinedload(models.Store.payment_methods),
#         joinedload(models.Store.delivery_config),
#         joinedload(models.Store.hours),
#         joinedload(models.Store.cities).joinedload(models.StoreCity.neighborhoods),
#     ).filter_by(id=store_id).first()
#
#     if not store:
#         print(f"❌ Loja {store_id} não encontrada")
#         return
#
#     settings = db.query(models.StoreSettings).filter_by(store_id=store_id).first()
#     if not settings:
#         print(f"⚠️ Configurações da loja {store_id} não encontradas")
#
#     try:
#         store_schema = StoreDetails.model_validate(store)
#         store_schema.ratingsSummary = RatingsSummaryOut(
#             **get_store_ratings_summary(db, store_id=store.id)
#         )
#         settings_schema = None
#         if settings:
#             settings_schema = StoreSettingsBase.model_validate(settings).model_dump(mode='json')
#     except Exception as e:
#         print(f"❌ Erro ao validar dados: {e}")
#         raise ConnectionRefusedError(f"Dados inválidos: {e}")
#
#     payload = store_schema.model_dump()
#     if settings_schema:
#         payload['store_settings'] = settings_schema  # Adiciona as configurações dentro do payload
#
#     target = sid if sid else f"admin_store_{store_id}"  # Room específica para admin
#     await sio.emit("store_full_updated", payload, namespace='/admin', to=target)
#
#
# async def admin_emit_orders_initial(db, store_id: int, sid: str | None = None):
#     print(f"🔄 [Admin] emit_orders_initial para store_id: {store_id}")
#
#
#     now = datetime.utcnow()
#
#     start_of_day = now.replace(hour=0, minute=0, second=0, microsecond=0)
#     end_of_day = now.replace(hour=23, minute=59, second=59, microsecond=999999)
#
#     orders = (
#         db.query(models.Order)
#         .options(
#             selectinload(models.Order.products)
#             .selectinload(models.OrderProduct.variants)
#             .selectinload(models.OrderVariant.options)
#         )
#         .filter(
#             models.Order.store_id == store_id,
#             models.Order.created_at >= start_of_day,
#             models.Order.created_at <= end_of_day,
#         )
#         .all()
#     )
#
#     payload = []
#     for order in orders:
#         try:
#             order_data = OrderDetails.model_validate(order).model_dump(mode='json')
#             payload.append(order_data)
#         except Exception as e:
#             print(f'❌ Erro ao validar pedido ID {order.id}: {e}')
#             continue
#
#     target = sid if sid else f"admin_store_{store_id}"
#     await sio.emit("orders_initial", payload, namespace='/admin', to=target)
#
#
# async def admin_emit_order_updated_from_obj(order: models.Order):
#     payload = OrderDetails.model_validate(order).model_dump(mode='json')
#     print('[SOCKET] emit_order_updated_from_obj payload:', payload)  # 👈 Adicione isso
#     await sio.emit("order_updated", payload, namespace='/admin', to=f"admin_store_{order.store_id}")
#
#
# async def admin_product_list_all(db, store_id: int, sid: str | None = None):
#     print(f"🔄 [Admin] product_list_all para store_id: {store_id}")
#
#     products = db.query(models.Product).options(
#         joinedload(models.Product.variant_links)
#         .joinedload(models.ProductVariantProduct.variant)
#         .joinedload(models.Variant.options)
#     ).filter_by(store_id=store_id, available=True).all()
#
#     product_ratings = {
#         product.id: get_product_ratings_summary(db, product_id=product.id)
#         for product in products
#     }
#
#     payload = [
#         {
#             **ProductOut.from_orm_obj(product).model_dump(exclude_unset=True),
#             "rating": product_ratings.get(product.id),
#         }
#         for product in products
#     ]
#
#     target = sid if sid else f"admin_store_{store_id}"
#     await sio.emit("products_updated", payload, namespace='/admin', to=target)
#
#
# async def admin_emit_store_updated(store: models.Store):
#     await sio.emit(
#         'store_updated',
#         StoreDetails.model_validate(store).model_dump(),
#         namespace='/admin',
#         to=f'admin_store_{store.id}'
#     )
#
#
# async def admin_emit_theme_updated(theme: models.StoreTheme):
#     pydantic_theme = StoreThemeOut.model_validate(theme).model_dump()
#     await sio.emit(
#         'theme_updated',
#         pydantic_theme,
#         namespace='/admin',
#         to=f'admin_store_{theme.store_id}'
#     )
#
#
