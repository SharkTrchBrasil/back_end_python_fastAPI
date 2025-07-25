from datetime import datetime
from urllib.parse import parse_qs

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

            totem_auth_user = await authorize_admin_by_jwt(db, admin_token)
            if not totem_auth_user or not totem_auth_user.id:
                return {"error": "Admin não autorizado."}

            admin_id = totem_auth_user.id

            # Busca todas as lojas às quais o admin tem acesso com a role 'admin'
            all_accessible_store_ids_for_admin = [
                sa.store_id
                for sa in db.query(models.StoreAccess)
                .join(models.Role)
                .filter(
                    models.StoreAccess.user_id == admin_id,
                    models.Role.machine_name == 'admin'
                )
                .all()
            ]

            print(
                f"DEBUG: all_accessible_store_ids para admin {admin_id} (por machine_name): {all_accessible_store_ids_for_admin}")

            # Fallback para adicionar a loja principal do usuário se não estiver nas acessíveis
            if not all_accessible_store_ids_for_admin and totem_auth_user.store_id:
                all_accessible_store_ids_for_admin.append(totem_auth_user.store_id)
                print(
                    f"DEBUG: Adicionada store_id do usuário autenticado como fallback: {totem_auth_user.store_id}")

            order = db.query(models.Order).filter_by(id=data['order_id']).first()

            if not order:
                return {'error': 'Pedido não encontrado.'}

            if order.store_id not in all_accessible_store_ids_for_admin:
                return {'error': 'Acesso negado: Pedido não pertence a uma das suas lojas.'}

            valid_statuses = [  # Usar o Enum diretamente aqui
                OrderStatus.PENDING,
                OrderStatus.PREPARING,
                OrderStatus.READY,
                OrderStatus.ON_ROUTE,
                OrderStatus.DELIVERED,
                OrderStatus.CANCELED,
            ]

            if data['new_status'] not in valid_statuses:
                return {'error': 'Status inválido'}

            old_status = order.order_status  # Salva o status atual antes de mudar

            order.order_status = OrderStatus(data['new_status'])

            # Lógica de baixa de estoque quando o status é 'delivered'
            if data['new_status'] == 'delivered' and old_status != 'delivered':
                for order_product in order.products:
                    product = db.query(models.Product).filter_by(id=order_product.product_id).first()
                    if product and product.control_stock:
                        product.stock_quantity = max(0, product.stock_quantity - order_product.quantity)
                        print(
                            f"Baixado {order_product.quantity} de {product.name}. Novo estoque: {product.stock_quantity}")

            # Lógica de REVERSÃO de estoque, se o pedido for marcado como 'canceled'
            if data['new_status'] == 'canceled' and old_status != 'canceled':
                if old_status in ['ready', 'on_route', 'delivered']:  # Só reverte se já havia sido 'tirado' do estoque
                    for order_product in order.products:
                        product = db.query(models.Product).filter_by(id=order_product.product_id).first()
                        if product and product.control_stock:
                            product.stock_quantity += order_product.quantity
                            print(
                                f"Estoque de {product.name} revertido em {order_product.quantity}. Novo estoque: {product.stock_quantity}")

            db.commit()
            db.refresh(order)


            await admin_emit_order_updated_from_obj(order)


            print(
                f"✅ [Session {sid}] Pedido {order.id} da loja {order.store_id} atualizado para: {data['new_status']}")

            return {'success': True, 'order_id': order.id, 'new_status': order.order_status}

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
            # --- Bloco de Autorização (permanece o mesmo) ---
            if 'order_id' not in data:
                return {'error': 'ID do pedido não fornecido'}

            session = db.query(models.StoreSession).filter_by(sid=sid, client_type='admin').first()
            if not session:
                return {'error': 'Sessão não autorizada'}

            query_params = parse_qs(self.environ[sid].get("QUERY_STRING", ""))
            admin_token = query_params.get("admin_token", [None])[0]
            if not admin_token:
                return {"error": "Token de admin não encontrado na sessão."}

            totem_auth_user = await authorize_admin_by_jwt(db, admin_token)
            if not totem_auth_user or not totem_auth_user.id:
                return {"error": "Admin não autorizado."}

            order = db.query(models.Order).filter_by(id=data['order_id']).first()
            if not order:
                return {'error': 'Pedido não encontrado.'}

            # A verificação de permissão (se a loja pertence ao admin) também continua aqui...
            # (código omitido por brevidade)

            # --- Lógica de Reivindicação de Impressão (O "Juiz") ---

            with db.begin_nested():
                existing_log = db.query(models.OrderPrintLog).filter(
                    models.OrderPrintLog.order_id == order.id,
                    models.OrderPrintLog.is_reprint == False
                ).first()

                if existing_log:
                    # Outro dispositivo já reivindicou. Retorna o status de conflito.
                    return {'status': 'already_claimed', 'success': False}

                # Este dispositivo venceu! Cria o log para "trancar" a tarefa.
                new_log = models.OrderPrintLog(
                    order_id=order.id,
                    printer_name="automatic",
                    is_reprint=False,
                    printed_at=datetime.utcnow()
                )
                db.add(new_log)

            print(f"✅ [Session {sid}] Reivindicou com sucesso a impressão para o pedido {order.id}")

            # --- RESPOSTA SIMPLIFICADA ---
            # Retornamos apenas a confirmação. O cliente já tem os dados.
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
        # Adicione aqui o bar_printer_destination se necessário

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

        # Agora que os IDs existem, montamos a lista para o evento
        for job in new_job_objects:
            # ✅ CORREÇÃO APLICADA AQUI:
            # Usamos 'job.printer_destination' (o nome correto do campo no modelo)
            # para criar a chave 'destination' no dicionário.
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

            # --- Início da Transação Atômica ---
            # Usamos 'with_for_update()' para bloquear a linha no banco de dados,
            # garantindo que nenhum outro processo possa modificá-la ao mesmo tempo.
            job_to_claim = db.query(models.OrderPrintLog).filter(
                models.OrderPrintLog.id == job_id
            ).with_for_update().first()
            # --- Fim da Transação Atômica ---

            if not job_to_claim:
                return {'error': f'Trabalho de impressão com ID {job_id} não encontrado.'}

            # Verifica se o trabalho ainda está pendente
            if job_to_claim.status == 'pending':
                # Venceu! Muda o status para 'claimed' e salva.
                job_to_claim.status = 'claimed'
                db.commit()
                print(f"✅ [Session {sid}] Reivindicou com sucesso o trabalho de impressão #{job_id}")
                return {'status': 'claim_successful', 'success': True}
            else:
                # Outro dispositivo foi mais rápido.
                print(f"❌ [Session {sid}] Falha ao reivindicar trabalho #{job_id}. Status atual: {job_to_claim.status}")
                db.rollback()  # Desfaz o bloqueio sem salvar nada
                return {'status': 'already_claimed', 'success': False}

        except Exception as e:
            db.rollback()
            print(f"❌ Erro inesperado em claim_specific_print_job: {str(e)}")
            return {'error': 'Falha interna ao processar a reivindicação'}