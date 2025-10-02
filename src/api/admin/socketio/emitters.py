import asyncio
import uuid
from datetime import timedelta, date
from typing import Optional
from venv import logger

from src.api.admin.services.analytics_service import get_peak_hours_for_store
from src.api.admin.services.holiday_service import HolidayService
from src.api.admin.services.insights_service import InsightsService
from src.api.admin.services.payable_service import payable_service

from src.api.crud import store_crud
from src.api.schemas.chatbot.chatbot_config import StoreChatbotConfigSchema
from src.api.schemas.chatbot.chatbot_conversation import ChatbotConversationSchema
from src.api.schemas.chatbot.chatbot_message import ChatbotMessageSchema

from src.api.schemas.products.category import Category
from src.api.schemas.orders.command import CommandOut
from src.api.schemas.financial.payable_category import PayableCategoryResponse
from src.api.schemas.analytics.peak_hours import PeakHoursAnalytics
from src.api.schemas.financial.receivable import ReceivableResponse, ReceivableCategoryResponse
# ✅ PASSO 1: Importar o schema necessário
from src.api.schemas.store.store import StoreWithRole
from src.api.schemas.store.store_details import StoreDetails
from src.api.schemas.store.store_payable import PayableResponse
from src.api.schemas.financial.supplier import SupplierResponse

from src.api.schemas.store.table import TableOut
from src.api.admin.services.customer_analytic_service import get_customer_analytics_for_store
from src.api.admin.services.dashboard_service import get_dashboard_data_for_period
from src.api.admin.services.product_analytic_services import get_product_analytics_for_store
from src.api.admin.services.subscription_service import SubscriptionService

from src.api.schemas.orders.order import OrderDetails
from src.core.database import get_db_manager
from src.core.models import Order
from src.core.utils.enums import ProductStatus
from src.socketio_instance import sio
from src.core import models

from src.api.schemas.products.product import ProductOut

from sqlalchemy.orm import selectinload
from src.api.schemas.products.variant import Variant


async def admin_emit_store_updated(db, store_id: int):
    """
    Envia os dados de configuração da loja, incluindo grupos de pagamento e cupons.
    AGORA REUTILIZANDO A LÓGICA DO SCHEMA 'StoreDetails'.
    """
    try:
        # 1. Busca os dados brutos da loja (a consulta já otimiza o carregamento)
        store = store_crud.get_store_base_details(db=db, store_id=store_id)
        if not store:
            return


        store_schema_instance = StoreDetails.model_validate(store)

        store_payload = store_schema_instance.model_dump(mode='json')

        # Busca os detalhes da assinatura (isso continua igual)
        subscription_payload, _ = SubscriptionService.get_subscription_details(store)

        # 4. Monta o payload final
        payload = {
            "store": store_payload,
            "subscription": subscription_payload,
        }

        await sio.emit('store_details_updated', payload, namespace='/admin', room=f"admin_store_{store_id}")
        print(f"✅ [Socket] Dados da loja {store_id} (usando lógica centralizada do Schema) atualizados.")

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
    try:
        # ✅ A CORREÇÃO: Trocamos models.Table por models.Tables para corresponder ao seu modelo atualizado.
        tables = db.query(models.Tables).filter_by(store_id=store_id, is_deleted=False).all()
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
    Busca os dados COMPLETOS do cardápio (produtos, categorias, complementos)
    e emite para a sala do admin em um único evento otimizado.
    """
    print(f"📢 [ADMIN] Preparando emissão 'products_updated' para a loja {store_id}...")

    # 1. Busca os produtos com TODOS os relacionamentos necessários para o admin
    products_from_db = db.query(models.Product).options(
        selectinload(models.Product.category_links).selectinload(models.ProductCategoryLink.category),
        selectinload(models.Product.default_options),
        selectinload(models.Product.variant_links)
            .selectinload(models.ProductVariantLink.variant)
            .selectinload(models.Variant.options)
            .selectinload(models.VariantOption.linked_product),
        selectinload(models.Product.prices).selectinload(models.FlavorPrice.size_option),

    ).filter(models.Product.store_id == store_id).filter(
        # ✅ 2. ADICIONE ESTE FILTRO PARA ESCONDER OS ARQUIVADOS
        models.Product.status != ProductStatus.ARCHIVED
    ).order_by(models.Product.priority).all()


    # 2. Busca TODOS os complementos (variants) da loja
    all_variants_from_db = db.query(models.Variant).options(
        selectinload(models.Variant.options)
            .selectinload(models.VariantOption.linked_product)
    ).filter(models.Variant.store_id == store_id).order_by(models.Variant.name).all()

    # 3. Busca TODAS as categorias da loja e sua estrutura interna
    all_categories_from_db = db.query(models.Category).options(
        selectinload(models.Category.option_groups).selectinload(models.OptionGroup.items),
        selectinload(models.Category.schedules).selectinload(models.CategorySchedule.time_shifts),
        selectinload(models.Category.product_links).selectinload(models.ProductCategoryLink.product)
    ).filter(models.Category.store_id == store_id).order_by(models.Category.priority).all()

    # 4. Serializa todos os dados
    products_payload = [ProductOut.model_validate(p).model_dump(mode='json') for p in products_from_db]
    variants_payload = [Variant.model_validate(v).model_dump(mode='json') for v in all_variants_from_db]
    categories_payload = [Category.model_validate(c).model_dump(mode='json') for c in all_categories_from_db]

    # 5. Emite o payload completo para o admin
    payload = {
        'store_id': store_id,
        'products': products_payload,
        'variants': variants_payload,
        'categories': categories_payload,
    }
    room_name = f'admin_store_{store_id}'
    await sio.emit('products_updated', payload, to=room_name, namespace='/admin')

    print(f"✅ [ADMIN] Emissão 'products_updated' (com variants e categories) para a sala: {room_name} concluída.")



async def emit_chatbot_config_update(db, store_id: int):
    """ Emite APENAS a configuração do chatbot para a loja. """
    try:
        config = db.query(models.StoreChatbotConfig).filter_by(store_id=store_id).first()
        if not config:
            return

        # Usa o Pydantic Schema para converter os dados para JSON
        payload = StoreChatbotConfigSchema.model_validate(config).model_dump(mode='json')

        # Emite em um novo canal chamado 'chatbot_config_updated'
        await sio.emit('chatbot_config_updated', payload, namespace='/admin', room=f"admin_store_{store_id}")
        print(f"✅ [Socket] Evento DEDICADO 'chatbot_config_updated' enviado para loja {store_id}.")
    except Exception as e:
        print(f"❌ Erro ao emitir chatbot_config_updated: {e}")

async def admin_emit_stuck_order_alert(order: Order):
    """
    Emite um alerta específico sobre um pedido parado para o painel do lojista.
    """
    room_name = f'store_{order.store_id}'
    payload = {
        "order_id": order.id,
        "public_id": order.public_id,
        "message": f"Atenção: O pedido #{order.public_id} está aguardando ação há mais de 20 minutos!"
    }

    await sio.emit('stuck_order_alert', payload, to=room_name)
    print(f"🚨 Alerta de pedido preso emitido para a loja {order.store_id} (Pedido: {order.public_id})")




# ✅ FUNÇÃO ATUALIZADA
async def emit_new_chat_message(db, message: models.ChatbotMessage):
    """
    Emite um evento em tempo real para o painel de admin quando uma nova mensagem de chat
    (do cliente ou da loja) é registrada.
    """
    print(f"🚀 [Socket] Emitindo nova mensagem de chat para loja {message.store_id}...")
    try:
        # 1. Converte a mensagem para o formato JSON (como já fazia)
        payload = ChatbotMessageSchema.model_validate(message).model_dump(mode='json')

        # ✅ 2. CORREÇÃO: Busca os metadados da conversa para pegar o nome do cliente
        metadata = db.query(models.ChatbotConversationMetadata).filter_by(
            chat_id=message.chat_id,
            store_id=message.store_id
        ).first()

        # Adiciona o nome do cliente ao payload que será enviado
        payload['customer_name'] = metadata.customer_name if metadata else 'Cliente'

        # 3. Define o evento e a sala de destino (como já fazia)
        event_name = "new_chat_message"
        room_name = f"admin_store_{message.store_id}"

        # 4. Emite o evento com o payload enriquecido
        await sio.emit(event_name, payload, namespace='/admin', room=room_name)

        print(f"✅ [Socket] Evento '{event_name}' (com nome do cliente) enviado para a sala {room_name}.")

    except Exception as e:
        print(f"❌ Erro ao emitir o evento '{event_name}': {e}")

# ✅ 2. ADICIONE ESTA NOVA FUNÇÃO NO FINAL DO ARQUIVO
async def admin_emit_conversations_initial(db, store_id: int, sid: str | None = None):
    """
    Busca a lista de resumos de todas as conversas de uma loja e a envia
    para o painel de admin. Ideal para a carga inicial.
    """
    print(f"🚀 [Socket] Enviando carga inicial de conversas para loja {store_id}...")
    try:
        # Busca todos os metadados das conversas, ordenando pelas mais recentes
        conversations = db.query(models.ChatbotConversationMetadata) \
            .filter_by(store_id=store_id) \
            .order_by(models.ChatbotConversationMetadata.last_message_timestamp.desc()) \
            .all()

        # Converte os dados para o formato JSON usando o schema
        payload = [ChatbotConversationSchema.model_validate(c).model_dump(mode='json') for c in conversations]

        event_name = "conversations_initial"
        target_room = f"admin_store_{store_id}"

        if sid:
            await sio.emit(event_name, payload, namespace='/admin', to=sid)
        else:
            await sio.emit(event_name, payload, namespace='/admin', room=target_room)

        print(f"✅ [Socket] Carga inicial de {len(conversations)} conversas enviada para a loja {store_id}.")

    except Exception as e:
        print(f'❌ Erro ao emitir conversations_initial: {e}')


# ✅ FUNÇÃO TOTALMENTE CORRIGIDA
async def admin_emit_stores_list_update(db, admin_user: models.User):
    """
    Envia a lista completa e atualizada de lojas (com todos os detalhes) para um admin específico.
    Útil após criar ou deletar uma loja.
    """
    try:
        # PASSO 1: Busca todos os objetos `StoreAccess` para o usuário.
        # Isso já nos dá a loja e a role associada, que é o que precisamos.
        # O `selectinload` garante que os objetos `store` e `role` sejam carregados de forma otimizada.
        store_accesses = db.query(models.StoreAccess).options(
            selectinload(models.StoreAccess.store),
            selectinload(models.StoreAccess.role)
        ).filter(models.StoreAccess.user_id == admin_user.id).all()

        # PASSO 2: Serializa a lista de `StoreAccess` para uma lista de dicionários
        # usando o schema `StoreWithRole`, que é o que o frontend espera.
        stores_list_payload = [
            StoreWithRole.model_validate(access).model_dump(mode='json')
            for access in store_accesses
        ]

        # PASSO 3: Busca todas as sessões ativas do admin para enviar a atualização.
        admin_sessions = db.query(models.StoreSession).filter_by(user_id=admin_user.id, client_type='admin').all()

        if not admin_sessions:
            print(
                f"ℹ️ Admin {admin_user.id} não possui sessão de socket ativa para receber atualização da lista de lojas.")
            return

        # PASSO 4: Emite o payload completo para cada sessão ativa.
        for session in admin_sessions:
            await sio.emit("admin_stores_list", {"stores": stores_list_payload}, to=session.sid, namespace='/admin')

        print(
            f"✅ [Socket] Lista de lojas COMPLETA ({len(stores_list_payload)} lojas) enviada para {len(admin_sessions)} sessão(ões) do admin {admin_user.id}.")

    except Exception as e:
        print(f"❌ Erro ao emitir admin_emit_stores_list_update: {e}")




# ✅ NOVA FUNÇÃO "SEGURA" ADICIONADA
async def safe_admin_emit_financials_updated(store_id: int, sid: str | None = None):
    """
    Wrapper seguro que executa admin_emit_financials_updated em sua própria
    sessão de banco de dados para isolar qualquer erro potencial.
    """
    print("🛡️ [DEBUG] Executando emissor 'financials_updated' em modo seguro...")
    db_manager = get_db_manager()
    session_generator = db_manager.get_session()
    db_session = next(session_generator)
    try:
        # Chama a função original com a sessão de banco de dados isolada
        await admin_emit_financials_updated(db=db_session, store_id=store_id, sid=sid)
    except Exception as e:
        # Se um erro ocorrer aqui, ele será contido e logado, mas não vai
        # quebrar a transação para os outros emissores.
        print(f"🔥🔥🔥 [ERRO ISOLADO] Erro no emissor 'financials_updated': {e}")
        import traceback
        traceback.print_exc()
    finally:
        # Garante que a sessão isolada seja fechada.
        db_session.close()
        print("✔️ [DEBUG] Emissor 'financials_updated' (modo seguro) concluído.")



async def safe_admin_emit_dashboard_data_updated(store_id: int, sid: str | None = None):
    """
    Wrapper seguro que executa admin_emit_dashboard_data_updated em sua própria
    sessão de banco de dados para isolar o erro conhecido.
    """
    print("🛡️ [DEBUG] Executando emissor 'dashboard_data' em modo seguro...")
    db_manager = get_db_manager()
    with db_manager as db_session:
        try:
            # Chama a função original com a sessão de banco de dados isolada
            await admin_emit_dashboard_data_updated(db=db_session, store_id=store_id, sid=sid)
            print("✔️ [DEBUG] Emissor 'dashboard_data' (modo seguro) concluído com sucesso.")
        except Exception as e:
            # Se um erro ocorrer aqui, ele será contido e logado.
            print(f"🔥🔥🔥 [ERRO ISOLADO] Erro no emissor 'dashboard_data': {e}")
            import traceback
            traceback.print_exc()