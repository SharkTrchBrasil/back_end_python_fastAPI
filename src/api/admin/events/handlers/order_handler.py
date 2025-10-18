import asyncio
import traceback
from urllib.parse import parse_qs

from sqlalchemy.orm import joinedload, selectinload

from src.api.admin.services import loyalty_service
from src.api.admin.services.cashback_service import calculate_and_apply_cashback_for_order
from src.api.admin.services.chatbot.chatbot_notification_service import send_order_status_update, send_new_order_summary
from src.api.admin.services.stock_service import decrease_stock_for_order, restock_for_canceled_order
from src.api.admin.services.store_access_service import StoreAccessService
from src.api.admin.utils.authorize_admin import authorize_admin_by_jwt

from src.core import models
from src.api.admin.socketio.emitters import (
    admin_emit_order_updated_from_obj, admin_emit_new_print_jobs
)
from src.core.cache.cache_manager import logger
from src.core.database import get_db_manager
from src.core.utils.enums import OrderStatus


async def handle_update_order_status(self, sid, data):
    with get_db_manager() as db:
        try:
            # --- Sua lógica de validação e autorização (continua perfeita) ---
            if not all(key in data for key in ['order_id', 'new_status']):
                return {'error': 'Dados incompletos'}
            session = db.query(models.StoreSession).filter_by(sid=sid, client_type='admin').first()
            if not session:
                return {'error': 'Sessão não autorizada'}
            query_params = parse_qs(self.environ[sid].get("QUERY_STRING", ""))
            admin_token = query_params.get("admin_token", [None])[0]
            if not admin_token:
                return {"error": "Token de admin não encontrado na sessão."}
            admin_user = await authorize_admin_by_jwt(db, admin_token)
            if not admin_user or not admin_user.id:
                return {"error": "Admin não autorizado."}
            all_accessible_store_ids_for_admin = StoreAccessService.get_accessible_store_ids_with_fallback(db,
                                                                                                         admin_user)

            order = db.query(models.Order).options(
                selectinload(models.Order.store)
                .selectinload(models.Store.chatbot_config),  # Carrega a config do chatbot
                joinedload(models.Order.customer)  # Carrega os dados do cliente
            ).filter(models.Order.id == data['order_id']).first()

            if not order:
                return {'error': 'Pedido não encontrado.'}

            if order.store_id not in all_accessible_store_ids_for_admin:
                return {'error': 'Acesso negado: Pedido não pertence a uma das suas lojas.'}

            # --- Sua lógica de atualização de status (continua perfeita) ---
            valid_statuses = [status.value for status in OrderStatus]
            if data['new_status'] not in valid_statuses:
                return {'error': 'Status inválido'}

            old_status_value = order.order_status.value
            new_status_str = data['new_status']
            if old_status_value == new_status_str:
                return {'success': True, 'message': 'O pedido já estava com este status.'}

            order.order_status = OrderStatus(new_status_str)

            # Ação que ocorre na entrega física
            if new_status_str == OrderStatus.DELIVERED.value:
                decrease_stock_for_order(order, db)
                # Apenas a baixa de estoque permanece aqui, pois ela é um evento físico.

            # Ações que ocorrem no fechamento financeiro/lógico do pedido
            if new_status_str == OrderStatus.FINALIZED.value:
                calculate_and_apply_cashback_for_order(order, db)
                loyalty_service.award_points_for_order(db=db, order=order)
                update_store_customer_stats(db, order)

            # Ação de cancelamento permanece a mesma
            if new_status_str == OrderStatus.CANCELED.value:
                restock_for_canceled_order(order, db)

            db.commit()

            db.refresh(order, attribute_names=['customer', 'store'])

            # ✅ ADICIONAR: Invalida cache de pedidos ativos
            cache_manager.client.delete(f"admin:{order.store_id}:orders:active")
            cache_manager.client.delete(f"admin:{order.store_id}:order:{order.id}:details")

            logger.info(f"🗑️ Cache invalidado para store {order.store_id} após mudança de status")

            # --- DEBUG: VERIFICANDO DADOS ANTES DE NOTIFICAR ---
            print("\n--- DEBUG: VERIFICANDO DADOS ANTES DE NOTIFICAR ---")
            print(f"ID do Pedido: {order.id}")
            if order.customer:
                print(f"Cliente encontrado: ID {order.customer.id}, Nome: {order.customer.name}")
                print(f"Telefone via 'order.customer.phone': {order.customer.phone}")
            else:
                print("Cliente (relação order.customer) NÃO encontrado.")
            print(f"Telefone via 'order.customer_phone' (campo direto): {order.customer_phone}")
            print("---------------------------------------------------\n")
            # --- FIM DEBUG ---




















            # --- Disparo das notificações (continua perfeito) ---
            asyncio.create_task(send_order_status_update(db, order))
            await admin_emit_order_updated_from_obj(order)

            print(
                f"✅ [Session {sid}] Pedido {order.id} da loja {order.store_id} atualizado de '{old_status_value}' para: '{new_status_str}'")

            return {'success': True, 'order_id': order.id, 'new_status': order.order_status.value}

        except Exception as e:
            db.rollback()
            print(f"❌ Erro ao atualizar pedido: {str(e)}\n{traceback.format_exc()}")
            return {'error': 'Falha interna ao processar a atualização do pedido.'}





async def process_new_order_automations(db, order):
    """
    Processa as automações de auto-accept e auto-print para um novo pedido.
    """
    store_settings = order.store.store_operation_config
    did_status_change = False

    # 1. Lógica de Auto-Accept (sem alterações)
    if store_settings.auto_accept_orders and order.order_status == 'pending':
        order.order_status = 'preparing'

        did_status_change = True
        print(f"Pedido {order.id} aceito automaticamente.")

    # 2. Lógica de Auto-Print (VERSÃO ATUALIZADA)
    jobs_to_emit = []
    if store_settings.auto_print_orders:
        products_by_destination = {}

        for order_product in order.products:
            destination = (order_product.product.category.printer_destination or
                           store_settings.main_printer_destination)
            if destination:
                if destination not in products_by_destination:
                    products_by_destination[destination] = []
                products_by_destination[destination].append(order_product)

        if products_by_destination:
            new_job_objects = []
            for dest, products_in_dest in products_by_destination.items():
                new_job = models.OrderPrintLog(
                    order_id=order.id,
                    printer_destination=dest,
                    status='pending'
                )
                db.add(new_job)
                new_job_objects.append(new_job)

            db.flush()

            for job in new_job_objects:
                jobs_to_emit.append({'id': job.id, 'destination': job.destination})

            print(f"Criados {len(jobs_to_emit)} trabalhos de impressão DIRECIONADOS para o pedido {order.id}.")

    # 3. Salva as mudanças no banco (sem alterações)
    db.commit()
    # Adicionamos 'products' pois essa função também os utiliza
    db.refresh(order, attribute_names=['customer', 'store', 'products'])


    asyncio.create_task(send_new_order_summary(db, order))

    # 4. Emite os eventos para os clientes (sem alterações)
    if did_status_change:
        await admin_emit_order_updated_from_obj(order)

        asyncio.create_task(send_order_status_update(db, order))

    if jobs_to_emit:
        await admin_emit_new_print_jobs(order.store_id, order.id, jobs_to_emit)



async def claim_specific_print_job(sid, data):
    """
    Permite que um cliente reivindique um trabalho de impressão específico pelo seu ID.
    Esta operação é atômica para evitar que dois dispositivos reivindiquem o mesmo trabalho.
    """
    print(f"📠 [Session {sid}] Recebida reivindicação para o trabalho de impressão: {data}")

    with get_db_manager() as db:
        try:
            if 'job_id' not in data:
                return {'error': 'ID do trabalho de impressão não fornecido'}

            job_id = data['job_id']

            job_to_claim = db.query(models.OrderPrintLog).filter(
                models.OrderPrintLog.id == job_id
            ).with_for_update().first()

            if not job_to_claim:
                return {'error': f'Trabalho de impressão com ID {job_id} não encontrado.'}

            if job_to_claim.status == 'pending':
                job_to_claim.status = 'claimed'
                db.commit()
                print(f"✅ [Session {sid}] Reivindicou com sucesso o trabalho de impressão #{job_id}")
                return {'status': 'claim_successful', 'success': True}
            else:
                print(f"❌ [Session {sid}] Falha ao reivindicar trabalho #{job_id}. Status atual: {job_to_claim.status}")
                db.rollback()
                return {'status': 'already_claimed', 'success': False}

        except Exception as e:
            db.rollback()
            print(f"❌ Erro inesperado em claim_specific_print_job: {str(e)}")
            return {'error': 'Falha interna ao processar a reivindicação'}



# ✅ NOVO HANDLER: Adicione esta função ao seu arquivo.
async def handle_update_print_job_status(self, sid, data):
    """
    Recebe uma atualização do cliente sobre o status de um trabalho de impressão
    (ex: 'completed' ou 'failed').
    """
    with get_db_manager() as db:
        try:
            # Validação dos dados recebidos
            if not all(key in data for key in ['job_id', 'status']):
                return {'error': 'Dados incompletos'}

            job_id = data['job_id']
            new_status = data['status']
            valid_statuses = ['completed', 'failed']

            if new_status not in valid_statuses:
                return {'error': f"Status '{new_status}' inválido."}

            # --- Bloco de Autorização (essencial para segurança) ---
            session = db.query(models.StoreSession).filter_by(sid=sid, client_type='admin').first()
            if not session:
                return {'error': 'Sessão não autorizada'}

            query_params = parse_qs(self.environ[sid].get("QUERY_STRING", ""))
            admin_token = query_params.get("admin_token", [None])[0]
            if not admin_token:
                return {"error": "Token de admin não encontrado."}

            admin_user = await authorize_admin_by_jwt(db, admin_token)
            if not admin_user:
                return {"error": "Admin não autorizado."}
            # --- Fim da Autorização ---

            # Busca o trabalho de impressão no banco
            job_to_update = db.query(models.OrderPrintLog).filter(
                models.OrderPrintLog.id == job_id
            ).first()

            if not job_to_update:
                return {'error': f'Trabalho de impressão #{job_id} não encontrado.'}

            # Garante que o admin tem permissão para modificar este trabalho
            accessible_stores = StoreAccessService.get_accessible_store_ids_with_fallback(db, admin_user)
            if job_to_update.order.store_id not in accessible_stores:
                return {'error': 'Acesso negado.'}

            # Atualiza o status e salva
            job_to_update.status = new_status
            db.commit()
            db.refresh(job_to_update)

            print(f"✅ Status do trabalho de impressão #{job_id} atualizado para '{new_status}'")

            # Opcional: Emite uma notificação para que outras telas atualizem o ícone de impressão
            await admin_emit_order_updated_from_obj(job_to_update.order)

            return {'success': True, 'job_id': job_id, 'new_status': new_status}

        except Exception as e:
            db.rollback()
            print(f"❌ Erro em handle_update_print_job_status: {str(e)}")
            return {'error': 'Falha interna'}


def update_store_customer_stats(db, order: models.Order):
    """
    Cria ou atualiza as estatísticas de um cliente em uma loja específica
    após um pedido ser concluído.
    """
    # Se o pedido não tem um cliente associado, não há o que fazer.
    if not order.customer_id:
        print(f"Pedido {order.id} não possui cliente, estatísticas não atualizadas.")
        return

    # Procura se já existe um registro para este cliente nesta loja
    store_customer = db.query(models.StoreCustomer).filter_by(
        store_id=order.store_id,
        customer_id=order.customer_id
    ).first()

    if store_customer:
        # Se já existe, ATUALIZA os dados
        print(f"Atualizando estatísticas para o cliente {order.customer_id} na loja {order.store_id}.")
        store_customer.total_orders += 1
        store_customer.total_spent += order.discounted_total_price  # Usa o preço final com desconto
        store_customer.last_order_at = order.created_at  # ou a data de conclusão do pedido
    else:
        # Se não existe, CRIA um novo registro
        print(f"Criando primeiro registro de estatísticas para o cliente {order.customer_id} na loja {order.store_id}.")
        store_customer = models.StoreCustomer(
            store_id=order.store_id,
            customer_id=order.customer_id,
            total_orders=1,
            total_spent=order.discounted_total_price,
            last_order_at=order.created_at,
        )
        db.add(store_customer)

    # Salva as alterações no banco de dados
    # O commit deve ser gerenciado pela sua rota/evento principal
    db.flush()  # Usa flush para preparar a escrita sem finalizar a transação principal
