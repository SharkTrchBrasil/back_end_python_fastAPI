from datetime import datetime, timedelta
from typing import Optional
from venv import logger
from zoneinfo import ZoneInfo

from src.api.admin.schemas.command import CommandOut
from src.api.admin.schemas.store_settings import StoreSettingsBase
from src.api.admin.schemas.subscription import StoreSubscriptionOut
from src.api.admin.schemas.table import TableOut
from src.api.admin.services.subscription_service import SubscriptionService

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
    try:
        # Carrega as relações necessárias, mas sem a subscription, pois o serviço cuidará disso.
        store = db.query(models.Store).options(
            joinedload(models.Store.payment_methods),
            joinedload(models.Store.delivery_config),
            joinedload(models.Store.hours),
            joinedload(models.Store.cities).joinedload(models.StoreCity.neighborhoods),
        ).filter_by(id=store_id).first()

        if not store:
            print(f"❌ Loja {store_id} não encontrada")
            return

        # Lógica para criar configurações padrão (settings) continua a mesma...
        settings = db.query(models.StoreSettings).filter_by(store_id=store_id).first()
        if not settings:
            settings = models.StoreSettings(store_id=store_id, is_delivery_active=False, is_takeout_active=True,
                                            is_table_service_active=False, is_store_open=False,
                                            auto_accept_orders=False, auto_print_orders=False)
            db.add(settings)
            db.commit()
            print(f"⚙️ Configurações padrão criadas para loja {store_id}")

        # ✨ 1. CHAME O SERVIÇO DE ASSINATURA PRIMEIRO
        subscription_payload, is_operational = SubscriptionService.get_subscription_details(db, store_id)

        # Se a loja não estiver operacional, você pode decidir o que fazer.
        # Por exemplo, emitir um evento de bloqueio e parar a execução.
        if not is_operational:
            print(f"🔒 Loja {store_id} não pode operar. Assinatura: {subscription_payload.get('status')}")
            # Você poderia emitir um evento de 'loja bloqueada' aqui e retornar.

        # Validação do schema da loja e obtenção de ratings...
        store_schema = StoreDetails.model_validate(store)
        try:
            store_schema.ratingsSummary = RatingsSummaryOut(**get_store_ratings_summary(db, store_id=store.id))
        except Exception:
            store_schema.ratingsSummary = RatingsSummaryOut(average_rating=0, total_ratings=0,
                                                            distribution={1: 0, 2: 0, 3: 0, 4: 0, 5: 0}, ratings=[])

        # ✨ 2. PREPARA O PAYLOAD FINAL USANDO OS DADOS DO SERVIÇO
        payload = {
            "store_id": store_id,
            "store": store_schema.model_dump(mode='json'),
            "subscription": subscription_payload  # <-- CORREÇÃO: Usa o payload do serviço
        }
        payload['store']['store_settings'] = StoreSettingsBase.model_validate(settings).model_dump(mode='json')

        # Emite os dados...
        if sid:
            await sio.emit("store_full_updated", payload, namespace='/admin', to=sid)
        else:
            await sio.emit("store_full_updated", payload, namespace='/admin', room=f"admin_store_{store_id}")

    except Exception as e:
        print(f'❌ Erro crítico em emit_store_full_updated: {str(e)}')
        # Lógica de erro continua a mesma...

async def admin_emit_orders_initial(db, store_id: int, sid: Optional[str] = None):
    """
    Emite os pedidos iniciais ativos para um admin, focando em pedidos que
    ainda requerem atenção, independentemente da data de criação.

    Args:
        db: A sessão do banco de dados.
        store_id (int): O ID da loja para a qual os pedidos serão emitidos.
        sid (Optional[str]): O ID da sessão do Socket.IO para emitir para um cliente específico.
                             Se None, emite para a room da loja.
    """
    try:
        # Define os status de pedidos que são considerados "ativos" e precisam de atenção do admin.
        # Ajuste esta lista para refletir os status que você deseja exibir por padrão.
        # Exemplos comuns: 'pending', 'preparing', 'ready', 'on_route', 'confirmed'
        active_order_statuses = ['pending', 'preparing', 'ready', 'on_route']

        orders = (
            db.query(models.Order)
            .options(
                selectinload(models.Order.products)
                .selectinload(models.OrderProduct.variants)
                .selectinload(models.OrderVariant.options)
            )
            .filter(
                models.Order.store_id == store_id,
                models.Order.order_status.in_(active_order_statuses) # ✨ Filtra por status ativos
            )
            .all()
        )

        orders_data = []

        for order in orders:
            # Busca o total de pedidos do cliente na loja
            # Considere se esta informação é sempre necessária para CADA pedido inicial.
            # Se for, mantenha. Se não, pode ser otimizado ou buscado sob demanda.
            store_customer = db.query(models.StoreCustomer).filter_by(
                store_id=store_id,
                customer_id=order.customer_id
            ).first()

            # Assumindo que OrderDetails é um Pydantic model para validação e serialização
            order_dict = OrderDetails.model_validate(order).model_dump(mode='json')
            order_dict["customer_order_count"] = store_customer.total_orders if store_customer else 1

            orders_data.append(order_dict)

        payload = {
            "store_id": store_id,
            "orders": orders_data
        }

        if sid:
            await sio.emit("orders_initial", payload, namespace='/admin', to=sid)
        else:
            # Emite para a room da loja, alcançando todos os admins conectados a essa loja.
            await sio.emit("orders_initial", payload, namespace='/admin', room=f"admin_store_{store_id}")

    except Exception as e:
        # Loga o erro detalhadamente para depuração no servidor
        print(f'❌ Erro ao emitir pedidos iniciais para loja {store_id} (SID: {sid}): {e.__class__.__name__}: {str(e)}')
        # Sempre emite uma resposta para o frontend, mesmo em caso de erro,
        # para que o frontend possa reagir (e.g., mostrar mensagem de erro, tela vazia).
        error_payload = {
            "store_id": store_id,
            "orders": [], # Garante que a lista de pedidos seja sempre enviada como lista vazia em caso de erro
            "error": str(e), # Opcional: envia a mensagem de erro para o frontend se útil para depuração
            "message": "Não foi possível carregar os pedidos iniciais. Tente novamente." # Mensagem amigável
        }
        if sid:
            await sio.emit("orders_initial", error_payload, namespace='/admin', to=sid)
        else:
            await sio.emit("orders_initial", error_payload, namespace='/admin', room=f"admin_store_{store_id}")



async def admin_emit_order_updated_from_obj(order: models.Order):
    try:
        order_data = OrderDetails.model_validate(order).model_dump(mode='json')
        await sio.emit("order_updated", order_data, namespace='/admin', room=f"admin_store_{order.store_id}")
    except Exception as e:
        logger.error(f'Erro ao emitir order_updated: {e}')


async def admin_product_list_all(db, store_id: int, sid: str | None = None):
   # print(f"🔄 [Admin] product_list_all para store_id: {store_id}")

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
  #  print(f"🔄 [Admin] emit_tables_and_commands para store_id: {store_id}")
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


# Importe o 'sio' se ainda não estiver no escopo do arquivo
from src.socketio_instance import sio
from src.core import models


async def emit_new_order_notification(db, store_id: int, order_id: int):
    """
    Encontra todos os admins com acesso à loja e emite uma notificação
    leve para suas salas de notificação pessoais.
    """
    try:
        # Encontra todos os StoreAccess para a loja
        store_accesses = db.query(models.StoreAccess).filter(
            models.StoreAccess.store_id == store_id
        ).all()

        admin_ids = {access.admin_id for access in store_accesses}

        # Fallback: Adiciona o dono da loja se não estiver na lista de acesso
        # Esta consulta já busca o objeto completo da loja
        store = db.query(models.Store).filter(models.Store.id == store_id).first()

        if store and store.user_id:
            admin_ids.add(store.user_id)

        if not admin_ids:
            print(f"🔔 Nenhum admin encontrado para notificar sobre a loja {store_id}.")
            return

        print(f"🔔 Notificando {len(admin_ids)} admins sobre novo pedido na loja {store_id}.")

        # ✨ CORREÇÃO APLICADA AQUI ✨
        # Prepara o payload com os dados ricos, incluindo o nome da loja
        payload = {
            'store_id': store_id,
            'order_id': order_id,
            'store_name': store.name if store else "uma de suas lojas"  # Adiciona o nome da loja
        }

        # Emite para a sala de notificação pessoal de cada admin
        for admin_id in admin_ids:
            notification_room = f"admin_notifications_{admin_id}"
            await sio.emit('new_order_notification', payload, to=notification_room, namespace='/admin')

    except Exception as e:
        print(f"❌ Erro ao emitir notificação de novo pedido: {e}")