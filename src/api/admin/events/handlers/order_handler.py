from datetime import datetime
from urllib.parse import parse_qs

from src.api.admin.services.store_access_service import StoreAccessService
from src.api.admin.utils.authorize_admin import authorize_admin_by_jwt
from src.api.shared_schemas.order import OrderStatus
from src.core import models
from src.api.admin.socketio.emitters import (
    admin_emit_order_updated_from_obj, admin_emit_new_print_jobs
)
from src.core.database import get_db_manager

async def handle_update_order_status(self, sid, data):
    with get_db_manager() as db:
        try:
            if not all(key in data for key in ['order_id', 'new_status']):
                return {'error': 'Dados incompletos'}

            session = db.query(models.StoreSession).filter_by(sid=sid, client_type='admin').first()
            if not session:
                return {'error': 'Sessão não autorizada'}

            query_params = parse_qs(self.environ[sid].get("QUERY_STRING", ""))
            admin_token = query_params.get("admin_token", [None])[0]
            if not admin_token:
                return {"error": "Token de admin não encontrado na sessão."}

            # ✅ CORREÇÃO 1: Renomeado para clareza, pois agora é um objeto User.
            admin_user = await authorize_admin_by_jwt(db, admin_token)
            if not admin_user or not admin_user.id:
                return {"error": "Admin não autorizado."}

            admin_id = admin_user.id

            # Busca todas as lojas às quais o admin tem acesso. Esta é a fonte de verdade.
            all_accessible_store_ids_for_admin = StoreAccessService.get_accessible_store_ids_with_fallback(
                db, admin_user
            )

            # ✅ CORREÇÃO 2: Bloco de fallback que causava o erro foi REMOVIDO.
            # A linha "if not ... and admin_user.store_id:" foi removida.

            order = db.query(models.Order).filter_by(id=data['order_id']).first()

            if not order:
                return {'error': 'Pedido não encontrado.'}

            if order.store_id not in all_accessible_store_ids_for_admin:
                return {'error': 'Acesso negado: Pedido não pertence a uma das suas lojas.'}

            valid_statuses = [status.value for status in OrderStatus]

            if data['new_status'] not in valid_statuses:
                return {'error': 'Status inválido'}

            old_status = order.order_status
            order.order_status = OrderStatus(data['new_status'])

            # Lógica de baixa e reversão de estoque...
            if data['new_status'] == 'delivered' and old_status != 'delivered':
                # ... (seu código de baixa de estoque)
                pass
            if data['new_status'] == 'canceled' and old_status != 'canceled':
                # ... (seu código de reversão de estoque)
                pass

            db.commit()
            db.refresh(order)

            await admin_emit_order_updated_from_obj(order)

            print(
                f"✅ [Session {sid}] Pedido {order.id} da loja {order.store_id} atualizado para: {data['new_status']}")

            return {'success': True, 'order_id': order.id, 'new_status': order.order_status.value}

        except Exception as e:
            db.rollback()
            print(f"❌ Erro ao atualizar pedido: {str(e)}")
            return {'error': 'Falha interna'}


async def handle_claim_print_job(self, sid, data):
    """
    Handler simplificado. Atua como um serviço de autorização e bloqueio
    para garantir que a impressão automática ocorra apenas uma vez.
    """
    with get_db_manager() as db:
        try:
            if 'order_id' not in data:
                return {'error': 'ID do pedido não fornecido'}

            session = db.query(models.StoreSession).filter_by(sid=sid, client_type='admin').first()
            if not session:
                return {'error': 'Sessão não autorizada'}

            query_params = parse_qs(self.environ[sid].get("QUERY_STRING", ""))
            admin_token = query_params.get("admin_token", [None])[0]
            if not admin_token:
                return {"error": "Token de admin não encontrado na sessão."}

            # ✅ CORREÇÃO: Renomeado para clareza.
            admin_user = await authorize_admin_by_jwt(db, admin_token)
            if not admin_user or not admin_user.id:
                return {"error": "Admin não autorizado."}

            order = db.query(models.Order).filter_by(id=data['order_id']).first()
            if not order:
                return {'error': 'Pedido não encontrado.'}

            # ✅ CORREÇÃO DE SEGURANÇA: Adicionada verificação de permissão.
            # Garante que o admin só possa reivindicar impressões de lojas que ele gerencia.
            accessible_stores = StoreAccessService.get_accessible_store_ids_with_fallback(db, admin_user)
            if order.store_id not in accessible_stores:
                return {'error': 'Acesso negado: Pedido não pertence a uma das suas lojas.'}

            # --- Lógica de Reivindicação de Impressão (O "Juiz") ---
            with db.begin_nested():
                existing_log = db.query(models.OrderPrintLog).filter(
                    models.OrderPrintLog.order_id == order.id,
                    models.OrderPrintLog.is_reprint == False
                ).first()

                if existing_log:
                    return {'status': 'already_claimed', 'success': False}

                new_log = models.OrderPrintLog(
                    order_id=order.id,
                    printer_name="automatic",
                    is_reprint=False,
                    printed_at=datetime.utcnow()
                )
                db.add(new_log)

            print(f"✅ [Session {sid}] Reivindicou com sucesso a impressão para o pedido {order.id}")

            return {
                'status': 'claim_successful',
                'success': True
            }

        except Exception as e:
            db.rollback()
            print(f"❌ Erro ao reivindicar impressão do pedido: {str(e)}")
            return {'error': 'Falha interna'}


async def process_new_order_automations(db, order):
    """
    Processa as automações de auto-accept e auto-print para um novo pedido.
    """
    # ✅ CORREÇÃO: Força o recarregamento das configurações da loja a partir do banco de dados.
    # Isso garante que a verificação 'auto_print_orders' use sempre o valor mais recente.
    db.refresh(order.store.settings)

    store_settings = order.store.settings
    did_status_change = False

    # 1. Lógica de Auto-Accept
    if store_settings.auto_accept_orders and order.order_status == 'pending':
        order.order_status = 'preparing'
        did_status_change = True
        print(f"Pedido {order.id} aceito automaticamente.")

    # 2. Lógica de Auto-Print
    jobs_to_emit = []
    if store_settings.auto_print_orders:
        destinations = []
        if store_settings.main_printer_destination:
            destinations.append(store_settings.main_printer_destination)
        if store_settings.kitchen_printer_destination:
            destinations.append(store_settings.kitchen_printer_destination)

        unique_destinations = set(destinations)

        new_job_objects = []
        for dest in unique_destinations:
            new_job = models.OrderPrintLog(
                order_id=order.id,
                printer_destination=dest,
                status='pending'
            )
            db.add(new_job)
            new_job_objects.append(new_job)

        db.flush()

        for job in new_job_objects:
            jobs_to_emit.append({'id': job.id, 'destination': job.printer_destination})

        print(f"Criados {len(jobs_to_emit)} trabalhos de impressão para o pedido {order.id}.")

    # 3. Salva as mudanças no banco
    db.commit()
    db.refresh(order)

    # 4. Emite os eventos para os clientes
    if did_status_change:
        await admin_emit_order_updated_from_obj(order)

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
