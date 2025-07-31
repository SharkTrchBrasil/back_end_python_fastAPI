import uuid
from datetime import datetime, timedelta
from typing import Optional
from venv import logger
from zoneinfo import ZoneInfo

from src.api.admin.schemas.command import CommandOut
from src.api.admin.schemas.store_settings import StoreSettingsBase

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
        # ✅ SUPER CONSULTA CORRIGIDA E OTIMIZADA
        store = db.query(models.Store).options(
            # --- Configurações e Dados da Loja ---
            selectinload(models.Store.payment_methods),
            joinedload(models.Store.settings),  # joinedload é bom para relações um-para-um
            selectinload(models.Store.hours),
            selectinload(models.Store.cities).selectinload(models.StoreCity.neighborhoods),
            selectinload(models.Store.coupons),

            # --- [VISÃO DO CARDÁPIO] ---
            # Carrega a árvore completa de produtos e seus complementos como aparecem no cardápio
            selectinload(models.Store.products).selectinload(
                models.Product.variant_links  # Store -> Product -> ProductVariantLink (A Regra)
            ).selectinload(
                models.ProductVariantLink.variant  # -> Variant (O Template)
            ).selectinload(
                models.Variant.options  # -> VariantOption (O Item)
            ).selectinload(
                models.VariantOption.linked_product  # -> Product (O item de Cross-Sell)
            ),

            # --- [PAINEL DE GERENCIAMENTO DE TEMPLATES] ---
            # Carrega TODOS os templates de variantes e suas opções, mesmo os não utilizados.
            # Essencial para a tela de "Gerenciar Grupos de Complementos".
            selectinload(models.Store.variants).selectinload(
                models.Variant.options
            ),

            # --- Assinatura e Plano (para o SubscriptionService) ---
            selectinload(models.Store.subscriptions)
            .joinedload(models.StoreSubscription.plan)
            .selectinload(models.Plans.included_features)
            .joinedload(models.PlansFeature.feature),
            selectinload(models.Store.subscriptions)
            .selectinload(models.StoreSubscription.subscribed_addons)
            .joinedload(models.PlansAddon.feature)

        ).filter(models.Store.id == store_id).first()

        if not store:
            print(f"❌ Loja {store_id} não encontrada na função admin_emit_store_full_updated")
            return

        # --- Processamento dos dados carregados ---

        # Lógica de settings usando os dados já carregados
        settings = store.settings
        if not settings:
            settings = models.StoreSettings(store_id=store_id)  # Cria configurações padrão se não existirem
            db.add(settings)
            db.commit()
            db.refresh(settings)

        # Lógica de assinatura
        subscription_payload, is_operational = SubscriptionService.get_subscription_details(store)
        if not is_operational:
            print(f"🔒 Loja {store_id} não pode operar. Assinatura: {subscription_payload.get('status')}")

        # Validação com Pydantic e cálculo de ratings
        store_schema = StoreDetails.model_validate(store)
        try:
            store_schema.ratingsSummary = RatingsSummaryOut(**get_store_ratings_summary(db, store_id=store.id))
        except Exception:
            store_schema.ratingsSummary = RatingsSummaryOut(average_rating=0, total_ratings=0, distribution={})

        # Montagem do payload final
        payload = {
            "store_id": store_id,
            "store": store_schema.model_dump(mode='json'),
            "subscription": subscription_payload
        }

        # Garante que os settings sejam incluídos corretamente
        payload['store']['store_settings'] = StoreSettingsBase.model_validate(settings).model_dump(mode='json')

        # Emissão do evento via Socket.IO
        if sid:
            await sio.emit("store_full_updated", payload, namespace='/admin', to=sid)
        else:
            await sio.emit("store_full_updated", payload, namespace='/admin', room=f"admin_store_{store_id}")

    except Exception as e:
        # Log de erro robusto
        print(f'❌ Erro crítico em emit_store_full_updated para loja {store_id}: {e.__class__.__name__}: {str(e)}')



async def admin_emit_orders_initial(db, store_id: int, sid: Optional[str] = None):
    try:
        # Define os status de pedidos que são considerados "ativos" e precisam de atenção do admin.
        active_order_statuses = ['pending', 'preparing', 'ready', 'on_route']

        orders = (
            db.query(models.Order)
            .options(
                # ✅ CORREÇÃO: Adicione esta linha para carregar os logs de impressão de cada pedido
                selectinload(models.Order.print_logs),

                # Mantém os carregamentos que você já tinha
                selectinload(models.Order.products)
                .selectinload(models.OrderProduct.variants)
                .selectinload(models.OrderVariant.options)
            )
            .filter(
                models.Order.store_id == store_id,
                models.Order.order_status.in_(active_order_statuses)  # ✨ Filtra por status ativos
            )
            .all()
        )

        orders_data = []

        for order in orders:
            # Busca o total de pedidos do cliente na loja
            store_customer = db.query(models.StoreCustomer).filter_by(
                store_id=store_id,
                customer_id=order.customer_id
            ).first()

            # Assumindo que seu Pydantic model 'OrderDetails' já foi atualizado
            # para incluir o campo 'print_logs'. A validação fará o trabalho.
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
            "orders": [],  # Garante que a lista de pedidos seja sempre enviada como lista vazia em caso de erro
            "error": str(e),  # Opcional: envia a mensagem de erro para o frontend se útil para depuração
            "message": "Não foi possível carregar os pedidos iniciais. Tente novamente."  # Mensagem amigável
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





async def emit_new_order_notification(db, store_id: int, order_id: int):
    """
    Encontra todos os admins com acesso à loja e emite uma notificação
    leve para suas salas de notificação pessoais.
    """
    try:
        # Esta consulta já busca TODOS os usuários com acesso à loja.
        # O dono da loja deve ter um registro aqui com a role de "owner" ou "admin".
        store_accesses = db.query(models.StoreAccess).filter(
            models.StoreAccess.store_id == store_id
        ).all()

        admin_ids = {access.user_id for access in store_accesses}

        if not admin_ids:
            print(f"🔔 Nenhum admin com acesso encontrado para notificar sobre a loja {store_id}.")
            return

        print(f"🔔 Notificando {len(admin_ids)} admins sobre novo pedido na loja {store_id}.")

        # ✨ 1. Gera um ID único para esta notificação
        notification_uuid = str(uuid.uuid4())

        # Buscamos a loja aqui apenas para pegar o nome para o payload da notificação.
        store = db.query(models.Store).filter(models.Store.id == store_id).first()

        payload = {
            'store_id': store_id,
            'order_id': order_id,
            'store_name': store.name if store else "uma de suas lojas",
                                                   'notification_uuid': notification_uuid  # ✨ 2. Adiciona o ID ao payl
        }

        # Emite para a sala de notificação pessoal de cada admin
        for admin_id in admin_ids:
            notification_room = f"admin_notifications_{admin_id}"
            await sio.emit('new_order_notification', payload, to=notification_room, namespace='/admin')

    except Exception as e:
        print(f"❌ Erro ao emitir notificação de novo pedido: {e.__class__.__name__}: {e}")




async def admin_emit_new_print_jobs(store_id: int, order_id: int, jobs: list):
    """
    Emite um evento para os clientes de uma loja, informando sobre novos
    trabalhos de impressão disponíveis.
    """
    room = f"admin_store_{store_id}"
    event = "new_print_jobs_available"
    payload = {
        "order_id": order_id,
        "jobs": jobs
    }
    await sio.emit(event, payload, room=room)
    print(f"Evento '{event}' emitido para a sala {room} com payload: {payload}")


async def admin_emit_products_updated(db, store_id: int):

    # ✅ CONSULTA CORRIGIDA E COMPLETA
    products = db.query(models.Product).options(
        selectinload(models.Product.variant_links)      # Product -> ProductVariantLink (A Regra)
        .selectinload(models.ProductVariantLink.variant) # -> Variant (O Template)
        .selectinload(models.Variant.options)            # -> VariantOption (O Item)
        .selectinload(models.VariantOption.linked_product) # -> Product (Cross-sell)
    ).filter(
        models.Product.store_id == store_id,
        models.Product.available == True
    ).all()

    # Pega avaliações dos produtos (lógica mantida)
    product_ratings = {
        product.id: get_product_ratings_summary(db, product_id=product.id)
        for product in products
    }

    products_data = []
    for product in products:
        # ✅ Validação com o novo schema ProductOut
        product_schema = ProductOut.model_validate(product)
        product_dict = product_schema.model_dump(mode='json')
        product_dict["rating"] = product_ratings.get(product.id)
        products_data.append(product_dict)

        # ✅ PASSO 1: Crie o payload no formato que o Dart espera.
        payload = {
            'store_id': store_id,
            'products': products_data
        }

        # ✅ PASSO 2: Emita o novo payload estruturado.
        room_name = f'admin_store_{store_id}'
        await sio.emit('products_updated', payload, to=room_name)  # Emitindo o 'payload' em vez de 'products_data'
        print(f"✅ Evento 'products_updated' com payload estruturado emitido para a sala: {room_name}")



