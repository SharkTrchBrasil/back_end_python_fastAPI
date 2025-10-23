# src/api/admin/events/handlers/order_handler.py

import asyncio
import traceback
from urllib.parse import parse_qs
from datetime import datetime, timezone

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
from src.core.cache.cache_manager import logger, cache_manager
from src.core.database import get_db_manager
from src.core.utils.enums import OrderStatus, AuditAction, AuditEntityType


# ═══════════════════════════════════════════════════════════════════════════════
# 🔥 PONTO VITAL 1: ATUALIZAR STATUS DO PEDIDO
# ═══════════════════════════════════════════════════════════════════════════════

async def handle_update_order_status(self, sid, data):
    """
    ✅ Atualiza o status de um pedido com auditoria completa

    - Rastreia mudanças de status
    - Registra quem fez a alteração
    - Monitora cancelamentos
    - Detecta finalizações
    """

    with get_db_manager() as db:
        try:
            # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
            # 1. VALIDAÇÃO DE DADOS
            # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

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

            all_accessible_store_ids_for_admin = StoreAccessService.get_accessible_store_ids_with_fallback(
                db, admin_user
            )

            # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
            # 2. BUSCA PEDIDO COM TODOS OS DADOS PARA AUDITORIA
            # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

            order = db.query(models.Order).options(
                selectinload(models.Order.store).selectinload(models.Store.chatbot_config),
                joinedload(models.Order.customer),
                selectinload(models.Order.products)
            ).filter(models.Order.id == data['order_id']).first()

            if not order:
                return {'error': 'Pedido não encontrado.'}

            if order.store_id not in all_accessible_store_ids_for_admin:
                return {'error': 'Acesso negado: Pedido não pertence a uma das suas lojas.'}

            # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
            # 3. VALIDAÇÃO DE STATUS
            # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

            valid_statuses = [status.value for status in OrderStatus]
            if data['new_status'] not in valid_statuses:
                return {'error': 'Status inválido'}

            # ✅ CORREÇÃO: Garante que ambos sejam strings para comparação
            old_status_value = order.order_status.value if isinstance(order.order_status, OrderStatus) else order.order_status
            new_status_str = data['new_status']

            if old_status_value == new_status_str:
                return {'success': True, 'message': 'O pedido já estava com este status.'}

            # ✅ CAPTURA DADOS PARA AUDITORIA ANTES DE MUDAR
            audit_data = {
                "order_id": order.id,
                "public_id": order.public_id,
                "old_status": old_status_value,
                "new_status": new_status_str,
                "order_type": order.order_type,
                "customer_name": order.customer_name or (order.customer.name if order.customer else "Sem nome"),
                "customer_phone": order.customer_phone,
                "total_price": float(order.total_price) / 100,
                "discounted_price": float(order.discounted_total_price) / 100,
                "payment_method": order.payment_method_name,
                "changed_by": admin_user.name,
                "changed_at": datetime.now(timezone.utc).isoformat(),
                "store_name": order.store.name
            }

            # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
            # 4. APLICA MUDANÇA DE STATUS
            # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

            # ✅ CORREÇÃO: Converte string para Enum
            order.order_status = OrderStatus(new_status_str)

            # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
            # 5. LÓGICA DE NEGÓCIO ESPECÍFICA POR STATUS
            # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

            business_actions = []

            # ✅ CORREÇÃO: Compara strings
            if new_status_str == OrderStatus.DELIVERED.value:
                decrease_stock_for_order(order, db)
                business_actions.append("Estoque baixado")

            if new_status_str == OrderStatus.FINALIZED.value:
                calculate_and_apply_cashback_for_order(order, db)
                loyalty_service.award_points_for_order(db=db, order=order)
                update_store_customer_stats(db, order)
                business_actions.extend([
                    "Cashback aplicado",
                    "Pontos de fidelidade creditados",
                    "Estatísticas do cliente atualizadas"
                ])

            if new_status_str == OrderStatus.CANCELED.value:
                restock_for_canceled_order(order, db)
                business_actions.append("Estoque reposto")

                if 'cancellation_reason' in data:
                    audit_data["cancellation_reason"] = data['cancellation_reason']

            audit_data["business_actions"] = business_actions

            # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
            # 6. REGISTRA LOG DE AUDITORIA
            # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

            # ✅ CORREÇÃO: Compara strings
            if new_status_str == OrderStatus.CANCELED.value:
                audit_action = AuditAction.CANCEL_ORDER
                description = f"Pedido #{order.public_id} CANCELADO"
            elif new_status_str == OrderStatus.FINALIZED.value:
                audit_action = AuditAction.UPDATE_ORDER_STATUS
                description = f"Pedido #{order.public_id} FINALIZADO - R$ {audit_data['discounted_price']:.2f}"
            else:
                audit_action = AuditAction.UPDATE_ORDER_STATUS
                description = f"Status do pedido #{order.public_id} alterado: {old_status_value} → {new_status_str}"

            # ✅ CRIA O LOG DE AUDITORIA
            audit_log = models.AuditLog(
                store_id=order.store_id,
                user_id=admin_user.id,
                user_name=admin_user.name,
                action=audit_action.value,
                entity_type=AuditEntityType.ORDER.value,
                entity_id=order.id,
                changes=audit_data,
                description=description,
                ip_address=self.environ[sid].get("REMOTE_ADDR"),
                user_agent=self.environ[sid].get("HTTP_USER_AGENT"),
                created_at=datetime.now(timezone.utc)
            )

            db.add(audit_log)
            db.commit()

            # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
            # 7. INVALIDAÇÃO DE CACHE
            # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

            db.refresh(order, attribute_names=['customer', 'store'])

            cache_manager.client.delete(f"admin:{order.store_id}:orders:active")
            cache_manager.client.delete(f"admin:{order.store_id}:order:{order.id}:details")

            logger.info(f"🗑️ Cache invalidado para store {order.store_id} após mudança de status")

            # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
            # 8. NOTIFICAÇÕES EM TEMPO REAL
            # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

            asyncio.create_task(send_order_status_update(db, order))
            await admin_emit_order_updated_from_obj(order)

            logger.info(
                f"✅ [AUDIT] Pedido #{order.public_id} ({order.id}) - "
                f"Status: {old_status_value} → {new_status_str} - "
                f"Por: {admin_user.name} - "
                f"Ações: {', '.join(business_actions) if business_actions else 'Nenhuma'}"
            )

            return {
                'success': True,
                'order_id': order.id,
                'new_status': order.order_status.value,
                'audit_id': audit_log.id
            }

        except Exception as e:
            db.rollback()

            # ✅ LOG DE ERRO TAMBÉM É AUDITADO
            try:
                error_log = models.AuditLog(
                    store_id=data.get('store_id'),
                    user_id=admin_user.id if 'admin_user' in locals() else None,
                    user_name=admin_user.name if 'admin_user' in locals() else "Desconhecido",
                    action=AuditAction.UPDATE_ORDER_STATUS.value,
                    entity_type=AuditEntityType.ORDER.value,
                    entity_id=data.get('order_id'),
                    changes={"error": str(e), "traceback": traceback.format_exc()},
                    description=f"❌ ERRO ao atualizar pedido: {str(e)}",
                    ip_address=self.environ[sid].get("REMOTE_ADDR"),
                    user_agent=self.environ[sid].get("HTTP_USER_AGENT"),
                    created_at=datetime.now(timezone.utc)
                )
                db.add(error_log)
                db.commit()
            except:
                pass

            logger.error(f"❌ Erro ao atualizar pedido: {str(e)}\n{traceback.format_exc()}")
            return {'error': 'Falha interna ao processar a atualização do pedido.'}


# ═══════════════════════════════════════════════════════════════════════════════
# 🔥 PONTO VITAL 2: PROCESSAR AUTOMAÇÕES DE NOVO PEDIDO
# ═══════════════════════════════════════════════════════════════════════════════

async def process_new_order_automations(db, order):
    """
    ✅ Processa automações de auto-accept e auto-print com auditoria

    - Registra auto-aceitação
    - Rastreia jobs de impressão criados
    - Monitora falhas de automação
    """

    try:
        store_settings = order.store.store_operation_config
        did_status_change = False
        automation_actions = []

        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        # 1. AUTO-ACCEPT
        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

        # ✅ CORREÇÃO: Usa Enum para comparação
        if store_settings.auto_accept_orders and order.order_status == OrderStatus.PENDING:
            old_status = order.order_status
            # ✅ CORREÇÃO: Atribui Enum diretamente
            order.order_status = OrderStatus.PREPARING
            did_status_change = True
            automation_actions.append("Auto-aceitação ativada")

            logger.info(f"✅ [AUTO-ACCEPT] Pedido #{order.public_id} aceito automaticamente")

        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        # 2. AUTO-PRINT
        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

        jobs_to_emit = []
        if store_settings.auto_print_orders:
            products_by_destination = {}

            for order_product in order.products:
                destination = (
                        order_product.product.category.printer_destination or
                        store_settings.main_printer_destination
                )
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
                    jobs_to_emit.append({
                        'id': job.id,
                        'destination': job.printer_destination
                    })

                automation_actions.append(f"{len(jobs_to_emit)} jobs de impressão criados")

                logger.info(
                    f"✅ [AUTO-PRINT] {len(jobs_to_emit)} jobs criados para pedido #{order.public_id}"
                )

        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        # 3. SALVA MUDANÇAS E REGISTRA AUDITORIA
        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

        db.commit()
        db.refresh(order, attribute_names=['customer', 'store', 'products'])

        # ✅ REGISTRA AUDITORIA SE HOUVE AUTOMAÇÃO
        if automation_actions:
            audit_log = models.AuditLog(
                store_id=order.store_id,
                user_id=None,
                user_name="SISTEMA",
                action=AuditAction.CREATE_ORDER.value,
                entity_type=AuditEntityType.ORDER.value,
                entity_id=order.id,
                changes={
                    "order_id": order.id,
                    "public_id": order.public_id,
                    "automation_actions": automation_actions,
                    "auto_accept_enabled": store_settings.auto_accept_orders,
                    "auto_print_enabled": store_settings.auto_print_orders,
                    "print_jobs_created": len(jobs_to_emit),
                    "print_destinations": [job['destination'] for job in jobs_to_emit]
                },
                description=f"Pedido #{order.public_id} criado - Automações: {', '.join(automation_actions)}",
                ip_address="127.0.0.1",
                user_agent="System Automation",
                created_at=datetime.now(timezone.utc)
            )
            db.add(audit_log)
            db.commit()

        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        # 4. NOTIFICAÇÕES
        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

        asyncio.create_task(send_new_order_summary(db, order))

        if did_status_change:
            await admin_emit_order_updated_from_obj(order)
            asyncio.create_task(send_order_status_update(db, order))

        if jobs_to_emit:
            await admin_emit_new_print_jobs(order.store_id, order.id, jobs_to_emit)

    except Exception as e:
        logger.error(f"❌ Erro ao processar automações do pedido #{order.id}: {e}")
        db.rollback()

        # ✅ REGISTRA ERRO NA AUDITORIA
        try:
            error_log = models.AuditLog(
                store_id=order.store_id,
                user_id=None,
                user_name="SISTEMA",
                action=AuditAction.CREATE_ORDER.value,
                entity_type=AuditEntityType.ORDER.value,
                entity_id=order.id,
                changes={
                    "error": str(e),
                    "traceback": traceback.format_exc()
                },
                description=f"❌ ERRO ao processar automações do pedido #{order.id}",
                ip_address="127.0.0.1",
                user_agent="System Automation",
                created_at=datetime.now(timezone.utc)
            )
            db.add(error_log)
            db.commit()
        except:
            pass


# ═══════════════════════════════════════════════════════════════════════════════
# 🔥 PONTO VITAL 3: REIVINDICAR JOB DE IMPRESSÃO
# ═══════════════════════════════════════════════════════════════════════════════

async def claim_specific_print_job(sid, data):
    """
    ✅ Permite reivindicar um job de impressão com auditoria

    - Rastreia qual dispositivo pegou o job
    - Monitora conflitos de impressão
    - Registra timestamp de claim
    """

    logger.info(f"📠 [Session {sid}] Recebida reivindicação para job: {data}")

    with get_db_manager() as db:
        try:
            if 'job_id' not in data:
                return {'error': 'ID do trabalho de impressão não fornecido'}

            job_id = data['job_id']

            # ✅ LOCK PESSIMISTA PARA EVITAR RACE CONDITION
            job_to_claim = db.query(models.OrderPrintLog).filter(
                models.OrderPrintLog.id == job_id
            ).with_for_update().first()

            if not job_to_claim:
                return {'error': f'Trabalho de impressão com ID {job_id} não encontrado.'}

            # ✅ CAPTURA DADOS ANTES DE REIVINDICAR
            was_claimed = job_to_claim.status != 'pending'

            if job_to_claim.status == 'pending':
                job_to_claim.status = 'claimed'

                # ✅ REGISTRA AUDITORIA DO CLAIM
                audit_log = models.AuditLog(
                    store_id=job_to_claim.order.store_id,
                    user_id=None,
                    user_name="Dispositivo de Impressão",
                    action=AuditAction.UPDATE_ORDER.value,
                    entity_type=AuditEntityType.ORDER.value,
                    entity_id=job_to_claim.order_id,
                    changes={
                        "print_job_id": job_id,
                        "printer_destination": job_to_claim.printer_destination,
                        "status_change": "pending → claimed",
                        "claimed_at": datetime.now(timezone.utc).isoformat(),
                        "session_id": sid
                    },
                    description=f"Job de impressão #{job_id} reivindicado - Destino: {job_to_claim.printer_destination}",
                    ip_address="Sistema",
                    user_agent="Print Client",
                    created_at=datetime.now(timezone.utc)
                )
                db.add(audit_log)
                db.commit()

                logger.info(f"✅ [Session {sid}] Job #{job_id} reivindicado com sucesso")
                return {'status': 'claim_successful', 'success': True}
            else:
                db.rollback()

                # ✅ REGISTRA TENTATIVA DE CLAIM DUPLICADO
                conflict_log = models.AuditLog(
                    store_id=job_to_claim.order.store_id,
                    user_id=None,
                    user_name="Dispositivo de Impressão",
                    action=AuditAction.UPDATE_ORDER.value,
                    entity_type=AuditEntityType.ORDER.value,
                    entity_id=job_to_claim.order_id,
                    changes={
                        "print_job_id": job_id,
                        "current_status": job_to_claim.status,
                        "conflict": "Tentativa de claim duplicado",
                        "session_id": sid
                    },
                    description=f"⚠️ Job #{job_id} já estava com status '{job_to_claim.status}' - Claim falhou",
                    ip_address="Sistema",
                    user_agent="Print Client",
                    created_at=datetime.now(timezone.utc)
                )
                db.add(conflict_log)
                db.commit()

                logger.warning(
                    f"❌ [Session {sid}] Job #{job_id} já estava {job_to_claim.status}"
                )
                return {'status': 'already_claimed', 'success': False}

        except Exception as e:
            db.rollback()
            logger.error(f"❌ Erro em claim_specific_print_job: {str(e)}")
            return {'error': 'Falha interna ao processar a reivindicação'}


# ═══════════════════════════════════════════════════════════════════════════════
# 🔥 PONTO VITAL 4: ATUALIZAR STATUS DO JOB DE IMPRESSÃO
# ═══════════════════════════════════════════════════════════════════════════════

async def handle_update_print_job_status(self, sid, data):
    """
    ✅ Atualiza status de job de impressão com auditoria

    - Rastreia sucesso/falha de impressão
    - Monitora dispositivos problemáticos
    - Registra tempo de impressão
    """

    with get_db_manager() as db:
        try:
            # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
            # 1. VALIDAÇÃO
            # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

            if not all(key in data for key in ['job_id', 'status']):
                return {'error': 'Dados incompletos'}

            job_id = data['job_id']
            new_status = data['status']
            valid_statuses = ['completed', 'failed']

            if new_status not in valid_statuses:
                return {'error': f"Status '{new_status}' inválido."}

            # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
            # 2. AUTORIZAÇÃO
            # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

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

            # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
            # 3. BUSCA E VALIDA JOB
            # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

            job_to_update = db.query(models.OrderPrintLog).filter(
                models.OrderPrintLog.id == job_id
            ).first()

            if not job_to_update:
                return {'error': f'Trabalho de impressão #{job_id} não encontrado.'}

            accessible_stores = StoreAccessService.get_accessible_store_ids_with_fallback(
                db, admin_user
            )
            if job_to_update.order.store_id not in accessible_stores:
                return {'error': 'Acesso negado.'}

            # ✅ CAPTURA ESTADO ANTERIOR
            old_status = job_to_update.status

            # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
            # 4. ATUALIZA STATUS
            # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

            job_to_update.status = new_status

            # ✅ REGISTRA AUDITORIA
            audit_log = models.AuditLog(
                store_id=job_to_update.order.store_id,
                user_id=admin_user.id,
                user_name=admin_user.name,
                action=AuditAction.UPDATE_ORDER.value,
                entity_type=AuditEntityType.ORDER.value,
                entity_id=job_to_update.order_id,
                changes={
                    "print_job_id": job_id,
                    "printer_destination": job_to_update.printer_destination,
                    "old_status": old_status,
                    "new_status": new_status,
                    "order_public_id": job_to_update.order.public_id,
                    "updated_by": admin_user.name,
                    "session_id": sid
                },
                description=f"Job de impressão #{job_id} {'✅ CONCLUÍDO' if new_status == 'completed' else '❌ FALHOU'}",
                ip_address=self.environ[sid].get("REMOTE_ADDR"),
                user_agent=self.environ[sid].get("HTTP_USER_AGENT"),
                created_at=datetime.now(timezone.utc)
            )
            db.add(audit_log)
            db.commit()
            db.refresh(job_to_update)

            logger.info(
                f"✅ Job #{job_id} - Status: {old_status} → {new_status} - "
                f"Pedido #{job_to_update.order.public_id}"
            )

            # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
            # 5. NOTIFICAÇÃO EM TEMPO REAL
            # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

            await admin_emit_order_updated_from_obj(job_to_update.order)

            return {
                'success': True,
                'job_id': job_id,
                'new_status': new_status,
                'audit_id': audit_log.id
            }

        except Exception as e:
            db.rollback()
            logger.error(f"❌ Erro em handle_update_print_job_status: {str(e)}")
            return {'error': 'Falha interna'}


# ═══════════════════════════════════════════════════════════════════════════════
# FUNÇÃO AUXILIAR (SEM AUDITORIA - APENAS ESTATÍSTICA)
# ═══════════════════════════════════════════════════════════════════════════════

def update_store_customer_stats(db, order: models.Order):
    """
    Cria ou atualiza as estatísticas de um cliente em uma loja específica
    após um pedido ser concluído.

    ⚠️ Esta função NÃO precisa de auditoria pois é apenas estatística,
       o evento principal já foi auditado em `handle_update_order_status`
    """

    if not order.customer_id:
        logger.debug(f"Pedido {order.id} não possui cliente, estatísticas não atualizadas.")
        return

    store_customer = db.query(models.StoreCustomer).filter_by(
        store_id=order.store_id,
        customer_id=order.customer_id
    ).first()

    if store_customer:
        logger.debug(
            f"Atualizando estatísticas: Cliente {order.customer_id} - "
            f"Loja {order.store_id}"
        )
        store_customer.total_orders += 1
        store_customer.total_spent += order.discounted_total_price
        store_customer.last_order_at = order.created_at
    else:
        logger.debug(
            f"Criando estatísticas: Cliente {order.customer_id} - "
            f"Loja {order.store_id}"
        )
        store_customer = models.StoreCustomer(
            store_id=order.store_id,
            customer_id=order.customer_id,
            total_orders=1,
            total_spent=order.discounted_total_price,
            last_order_at=order.created_at,
        )
        db.add(store_customer)

    db.flush()