import asyncio
import uuid
from datetime import timedelta, date
from typing import Optional
from venv import logger

from sqlalchemy.orm.exc import DetachedInstanceError

from src.api.schemas.category import CategoryOut
from src.api.admin.services.analytics_service import get_peak_hours_for_store
from src.api.admin.services.holiday_service import HolidayService
from src.api.admin.services.insights_service import InsightsService
from src.api.admin.services.payable_service import payable_service
from src.api.admin.utils.payment_method_group import _build_payment_groups_from_activations_simplified
from src.api.crud import store_crud
from src.api.schemas.command import CommandOut
from src.api.schemas.payable_category import PayableCategoryResponse
from src.api.schemas.peak_hours import PeakHoursAnalytics
from src.api.schemas.receivable import ReceivableResponse, ReceivableCategoryResponse
from src.api.schemas.store_details import StoreDetails
from src.api.schemas.store_payable import PayableResponse
from src.api.schemas.supplier import SupplierResponse

from src.api.schemas.table import TableOut
from src.api.admin.services.customer_analytic_service import get_customer_analytics_for_store
from src.api.admin.services.dashboard_service import get_dashboard_data_for_period
from src.api.admin.services.product_analytic_services import get_product_analytics_for_store
from src.api.admin.services.subscription_service import SubscriptionService

from src.api.app.services.rating import get_product_ratings_summary, get_store_ratings_summary, \
    get_all_ratings_summaries_for_store
from src.api.schemas.order import OrderDetails
from src.api.schemas.rating import RatingsSummaryOut
from src.socketio_instance import sio
from src.core import models

from src.api.schemas.product import ProductOut

from sqlalchemy.orm import selectinload
from src.api.schemas.variant import Variant



async def admin_emit_store_updated(db, store_id: int):
    """
    Envia APENAS os dados de configuração da loja.
    É leve e pode ser chamado após qualquer alteração no cadastro.
    """
    try:
        # Usa a nova consulta otimizada
        store = store_crud.get_store_base_details(db=db, store_id=store_id)
        if not store:
            return

        subscription_payload, _ = SubscriptionService.get_subscription_details(store)
        store_schema = StoreDetails.model_validate(store)

        # Lógica de grupos de pagamento
        payment_groups_structured = _build_payment_groups_from_activations_simplified(store.payment_activations)
        store_schema.payment_method_groups = payment_groups_structured

        payload = {
            "store": store_schema.model_dump(mode='json'),
            "subscription": subscription_payload,
        }
        await sio.emit('store_details_updated', payload, namespace='/admin', room=f"admin_store_{store_id}")
        print(f"✅ [Socket] Dados da loja {store_id} atualizados e enviados.")

    except Exception as e:
        print(f'❌ Erro ao emitir store_details_updated: {e}')


async def admin_emit_dashboard_data_updated(db, store_id: int, sid: str | None = None):
    """
    Envia APENAS os dados analíticos e insights para o dashboard.
    Pode ser chamado ao conectar ou ao clicar em "Atualizar" no dashboard.
    """
    try:
        # --- 1. Prepara e executa as tarefas pesadas em paralelo ---
        tasks = [
            get_product_analytics_for_store(db, store_id),
            get_customer_analytics_for_store(db, store_id),
            HolidayService.get_upcoming_holiday_insight(),
            InsightsService.generate_dashboard_insights(db, store_id)
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # --- 2. Desempacota os resultados ---
        product_analytics_data, customer_analytics_data, holiday_insight, product_insights = (
            res if not isinstance(res, Exception) else None for res in results
        )
        product_insights = product_insights or []

        # --- 3. Monta e envia o payload ---
        end_date = date.today()
        start_date = end_date - timedelta(days=29)
        dashboard_data = get_dashboard_data_for_period(db, store_id, start_date, end_date)
        peak_hours_data = PeakHoursAnalytics.model_validate(get_peak_hours_for_store(db, store_id))

        insights_payload = []
        if holiday_insight:
            insights_payload.append(holiday_insight)
        insights_payload.extend(product_insights)

        payload = {
            "dashboard": dashboard_data.model_dump(mode='json'),
            "product_analytics": product_analytics_data.model_dump(mode='json') if product_analytics_data else {},
            "customer_analytics": customer_analytics_data.model_dump(mode='json') if customer_analytics_data else {},
            "peak_hours": peak_hours_data.model_dump(by_alias=True, mode='json'),
            "insights": [insight.model_dump(mode='json') for insight in insights_payload]
        }

        # Emissão do evento
        target_room = f"admin_store_{store_id}"
        if sid:
            await sio.emit("dashboard_data_updated", payload, namespace='/admin', to=sid)
        else:
            await sio.emit("dashboard_data_updated", payload, namespace='/admin', room=target_room)
        print(f"✅ [Socket] Dados do dashboard da loja {store_id} atualizados e enviados.")

    except Exception as e:
        print(f'❌ Erro ao emitir dashboard_data_updated: {e}')


async def admin_emit_dashboard_payables_data_updated(db, store_id: int, sid: str | None = None):
    """
    Busca e envia os dados do widget de Contas a Pagar para o dashboard.
    """
    print(f"🚀 [Socket] Atualizando dados de Contas a Pagar para loja {store_id}...")
    try:
        # 1. Busca os dados usando o service que já temos
        # Nota: Estamos chamando uma função síncrona de dentro de uma assíncrona.
        # Para queries pesadas, o ideal seria usar asyncio.to_thread, mas para esta, é aceitável.
        payables_metrics = payable_service.get_payables_metrics(db, store_id)

        # 2. Prepara o payload para ser enviado via JSON
        payload = payables_metrics.model_dump(mode='json')

        # 3. Emite o evento com um nome específico
        event_name = "payables_data_updated"
        target_room = f"admin_store_{store_id}"

        if sid:
            await sio.emit(event_name, payload, namespace='/admin', to=sid)
        else:
            await sio.emit(event_name, payload, namespace='/admin', room=target_room)

        print(f"✅ [Socket] Dados de Contas a Pagar da loja {store_id} enviados.")

    except Exception as e:
        print(f'❌ Erro ao emitir payables_data_updated: {e}')



async def admin_emit_financials_updated(db, store_id: int, sid: str | None = None):
    """
    Carrega e envia as listas completas de Contas a Pagar, Fornecedores e Categorias.
    """
    print(f"🚀 [Socket] Atualizando dados financeiros para loja {store_id}...")
    try:
        # 1. Busca a loja e carrega as relações necessárias de forma otimizada
        store_with_financials = (
            db.query(models.Store)
            .options(
                selectinload(models.Store.payables).joinedload(models.StorePayable.supplier),
                selectinload(models.Store.suppliers),
                selectinload(models.Store.payable_categories),
                selectinload(models.Store.receivables).joinedload(models.StoreReceivable.customer),
                selectinload(models.Store.receivable_categories),
            )
            .filter(models.Store.id == store_id)
            .one_or_none()
        )

        if not store_with_financials:
            return

        # 2. Prepara o payload usando os Schemas Pydantic para garantir o formato correto
        payload = {
            "payables": [PayableResponse.model_validate(p).model_dump(mode='json') for p in
                         store_with_financials.payables],
            "suppliers": [SupplierResponse.model_validate(s).model_dump(mode='json') for s in
                          store_with_financials.suppliers],
            "categories": [PayableCategoryResponse.model_validate(c).model_dump(mode='json') for c in
                           store_with_financials.payable_categories],

            "receivables": [ReceivableResponse.model_validate(r).model_dump(mode='json') for r in
                            store_with_financials.receivables],
            "receivable_categories": [ReceivableCategoryResponse.model_validate(c).model_dump(mode='json') for c in
                                      store_with_financials.receivable_categories],
        }



        # 3. Emite o evento com um nome específico
        event_name = "financials_updated"
        target_room = f"admin_store_{store_id}"

        # Lógica de emissão (pode variar um pouco no seu código)
        if sid:
            await sio.emit(event_name, payload, namespace='/admin', to=sid)
        else:
            await sio.emit(event_name, payload, namespace='/admin', room=target_room)

        print(f"✅ [Socket] Dados financeiros da loja {store_id} enviados.")

    except Exception as e:
        print(f'❌ Erro ao emitir financials_updated: {e}')


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
            await sio.emit("tables_and_commands", {"store_id": store_id, "tables": [], "commands": []},
                           namespace="/admin", to=sid)
        else:
            await sio.emit("tables_and_commands", {"store_id": store_id, "tables": [], "commands": []},
                           namespace="/admin", room=f"admin_store_{store_id}")


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
    """
    Busca a lista COMPLETA de produtos E a lista COMPLETA de complementos (variants)
    e emite para a sala do admin em um único evento otimizado.
    """
    print(f"📢 [ADMIN] Preparando emissão 'products_updated' para a loja {store_id}...")
    # ✅ --- PASSO 1: A "IMPRESSÃO DIGITAL" ---
    # Este print nos dirá se o servidor está executando esta versão do código.
    print("\n--- [DEBUG] EXECUTANDO VERSÃO NOVA DO EMITTER (COM SELECTINLOAD E PRINTS) ---\n")

    print(f"📢 [ADMIN] Preparando emissão 'products_updated' para a loja {store_id}...")

    # 1. Busca os produtos com todos os relacionamentos aninhados.
    # Sua consulta está perfeita e é a forma mais eficiente.
    products_from_db = db.query(models.Product).options(
        # 🔄 ajustado para carregar categorias
        selectinload(models.Product.category_links).selectinload(models.ProductCategoryLink.category),

        selectinload(models.Product.default_options),
        selectinload(models.Product.variant_links)
            .selectinload(models.ProductVariantLink.variant)
            .selectinload(models.Variant.options)
            .selectinload(models.VariantOption.linked_product)
    ).filter(models.Product.store_id == store_id).order_by(models.Product.priority).all()

    # 2. Busca TODOS os complementos da loja, também com seus relacionamentos.
    all_variants_from_db = db.query(models.Variant).options(
        selectinload(models.Variant.options)
            .selectinload(models.VariantOption.linked_product)
    ).filter(models.Variant.store_id == store_id).order_by(models.Variant.name).all()

    # ✅ NOVO: 3. Busca TODAS as categorias da loja
    all_categories_from_db = db.query(models.Category) \
        .filter(models.Category.store_id == store_id) \
        .order_by(models.Category.priority).all()

    # ✅ --- PASSO 2: INSPECIONANDO OS DADOS ANTES DA "QUEBRA" ---
    print("\n--- [DEBUG] Verificando produtos antes de serializar ---\n")
    for p in products_from_db:
        print(f"  - Verificando Produto ID: {p.id}, Nome: {p.name}")
        try:
            # Tentamos acessar as relações que o Pydantic precisa
            if p.category_links:
                print(f"    -> Link de Categoria 0: {p.category_links[0]}")
                print(f"    -> Categoria do Link 0: {p.category_links[0].category.name}")  # Teste crucial
            else:
                print("    -> SEM LINKS DE CATEGORIA!")

            if p.variant_links:
                print(f"    -> Link de Variante 0: {p.variant_links[0]}")
                print(f"    -> ID do Link de Variante 0: {p.variant_links[0].id}")  # Teste crucial
            else:
                print("    -> SEM LINKS DE VARIANTE!")

        except DetachedInstanceError:
            print(
                "    -> 🔥 ERRO: DetachedInstanceError! Prova de que a relação não foi carregada (lazy loading falhou).")
        except Exception as e:
            print(f"    -> 🔥 ERRO ao acessar relação: {e}")
        print("-" * 20)
    print("\n--- [DEBUG] Fim da verificação. Tentando serializar agora... ---\n")

    # 5. Serializa TODOS os dados
    products_payload = [ProductOut.model_validate(p).model_dump(mode='json') for p in products_from_db]
    variants_payload = [Variant.model_validate(v).model_dump(mode='json') for v in all_variants_from_db]
    categories_payload = [CategoryOut.model_validate(c).model_dump(mode='json') for c in
                          all_categories_from_db]  # ✅ Serializa as categorias

    # 6. Emite o payload completo
    payload = {
        'store_id': store_id,
        'products': products_payload,
        'variants': variants_payload,
        'categories': categories_payload,  # ✅ Envia a lista COMPLETA de categorias
    }
    room_name = f'admin_store_{store_id}'
    await sio.emit('products_updated', payload, to=room_name, namespace='/admin')

    print(f"✅ [ADMIN] Emissão 'products_updated' (com variants e categories) para a sala: {room_name} concluída.")



