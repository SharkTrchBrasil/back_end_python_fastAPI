from datetime import datetime
from venv import logger
from zoneinfo import ZoneInfo

from src.api.admin.schemas.command import CommandOut
from src.api.admin.schemas.store_settings import StoreSettingsBase
from src.api.admin.schemas.table import TableOut

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
        # Carrega todas as relações necessárias
        store = db.query(models.Store).options(
            joinedload(models.Store.payment_methods),
            joinedload(models.Store.delivery_config),
            joinedload(models.Store.hours),
            joinedload(models.Store.cities).joinedload(models.StoreCity.neighborhoods),
            joinedload(models.Store.subscriptions)
                .joinedload(models.StoreSubscription.plan)
                .joinedload(models.SubscriptionPlan.features),
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

        # Valida o schema da loja
        store_schema = StoreDetails.model_validate(store)

        # Adiciona informações de avaliação (com fallback)
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

        # Encontra a assinatura ativa mais recente
        active_sub = None
        for sub in store.subscriptions:
            if sub.status in ['active', 'new_charge']:
                if not active_sub or (sub.current_period_end > active_sub.current_period_end):
                    active_sub = sub

        # Prepara as informações da assinatura
        store_subscription_info = None
        if active_sub:
            plan = active_sub.plan
            features_list = [
                {"feature_key": f.feature_key, "is_enabled": f.is_enabled}
                for f in plan.features
            ]

            store_subscription_info = {
                "id": active_sub.id,
                "status": active_sub.status,
                "current_period_start": active_sub.current_period_start.isoformat(),
                "current_period_end": active_sub.current_period_end.isoformat(),
                "is_recurring": active_sub.is_recurring,
                "plan": {
                    "id": plan.id,
                    "plan_name": plan.plan_name,
                    "price": plan.price,
                    "interval": plan.interval,
                    "repeats": plan.repeats,
                    "features": features_list
                }
            }

        # Prepara o payload final
        payload = {
            "store_id": store_id,
            "store": store_schema.model_dump(),
            "subscription": store_subscription_info
        }
        payload['store']['store_settings'] = StoreSettingsBase.model_validate(settings).model_dump(mode='json')

        # Emite os dados
        if sid:
            await sio.emit("store_full_updated", payload, namespace='/admin', to=sid)
        else:
            await sio.emit("store_full_updated", payload, namespace='/admin', room=f"admin_store_{store_id}")

    except Exception as e:
        print(f'❌ Erro crítico em emit_store_full_updated: {str(e)}')
        error_payload = {
            "store_id": store_id,
            "store": {},
            "error": str(e)
        }
        if sid:
            await sio.emit("store_full_updated", error_payload, namespace='/admin', to=sid)
        else:
            await sio.emit("store_full_updated", error_payload, namespace='/admin', room=f"admin_store_{store_id}")

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




async def admin_emit_tables_and_commands(db, store_id: int, sid: str | None = None):
    print(f"🔄 [Admin] emit_tables_and_commands para store_id: {store_id}")
    try:
        tables = db.query(models.Table).filter_by(store_id=store_id, is_deleted=False).all()
        commands = db.query(models.Command).filter_by(store_id=store_id).all()

        tables_data = [TableOut.model_validate(table).model_dump(mode='json') for table in tables]
        commands_data = [CommandOut.model_validate(cmd).model_dump(mode='json') for cmd in commands]

        payload = {
            "store_id": store_id,
            "tables": tables_data,
            "commands": commands_data,
        }

        if sid:
            await sio.emit("tables_and_commands", payload, namespace="/admin", to=sid)
        else:
            await sio.emit("tables_and_commands", payload, namespace="/admin", room=f"admin_store_{store_id}")

    except Exception as e:
        print(f'❌ Erro em emit_tables_and_commands: {str(e)}')
        if sid:
            await sio.emit("tables_and_commands", {"store_id": store_id, "tables": [], "commands": []}, namespace="/admin", to=sid)
        else:
            await sio.emit("tables_and_commands", {"store_id": store_id, "tables": [], "commands": []}, namespace="/admin", room=f"admin_store_{store_id}")
