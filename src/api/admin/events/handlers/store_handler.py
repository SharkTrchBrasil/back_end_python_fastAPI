import asyncio
import traceback
from sqlalchemy import delete
from urllib.parse import parse_qs

from src.api.admin.services.store_access_service import StoreAccessService
from src.api.admin.services.store_session_service import SessionService
from src.api.admin.services.subscription_service import SubscriptionService
from src.api.admin.utils.authorize_admin import authorize_admin_by_jwt
from src.api.admin.utils.emit_updates import emit_store_updates

from src.core import models
from src.api.admin.socketio.emitters import (
    admin_emit_store_updated, admin_emit_dashboard_data_updated,
    admin_emit_orders_initial, admin_emit_tables_and_commands, admin_emit_products_updated,
    admin_emit_financials_updated, admin_emit_dashboard_payables_data_updated, admin_emit_conversations_initial,

)
from src.core.database import get_db_manager


async def handle_set_consolidated_stores(sio_namespace, sid, data):
    """
    Atualiza as PREFERÊNCIAS de lojas consolidadas de um admin no banco de dados.
    """
    try:
        selected_store_ids = set(data.get("store_ids", []))
        if not isinstance(data.get("store_ids"), list):
            return {"error": "'store_ids' deve ser uma lista"}

        with get_db_manager() as db:
            session = SessionService.get_session(db, sid)

            if not session or not session.user_id:
                return {"error": "Sessão não autorizada"}

            admin_id = session.user_id

            db.execute(
                delete(models.AdminConsolidatedStoreSelection).where(
                    models.AdminConsolidatedStoreSelection.admin_id == admin_id
                )
            )

            for store_id in selected_store_ids:
                new_selection = models.AdminConsolidatedStoreSelection(
                    admin_id=admin_id, store_id=store_id
                )
                db.add(new_selection)

            db.commit()

            print(f"✅ Preferências de consolidação do admin {admin_id} atualizadas para: {selected_store_ids}")

            # ✅ CORREÇÃO: Usa o sio_namespace para emitir
            await sio_namespace.emit(
                "consolidated_stores_updated",
                {"store_ids": list(selected_store_ids)},
                to=sid,
            )

            return {"success": True, "selected_stores": list(selected_store_ids)}

    except Exception as e:
        if 'db' in locals() and db.is_active:
            db.rollback()
        print(f"❌ Erro em on_set_consolidated_stores: {str(e)}")
        return {"error": f"Falha interna: {str(e)}"}


async def handle_update_operation_config(sio_namespace, sid, data):
    with get_db_manager() as db:
        session = SessionService.get_session(db, sid, client_type="admin")

        if not session:
            return {'error': 'Sessão não encontrada ou não autorizada'}

        requested_store_id = data.get("store_id")
        if not requested_store_id:
            return {'error': 'ID da loja é obrigatório para atualizar configurações.'}

        # ✅ CORREÇÃO: Usa o sio_namespace para acessar o environ
        query_params = parse_qs(sio_namespace.environ[sid].get("QUERY_STRING", ""))
        admin_token = query_params.get("admin_token", [None])[0]
        if not admin_token:
            return {"error": "Token de admin não encontrado na sessão."}

        admin_user = await authorize_admin_by_jwt(db, admin_token)
        if not admin_user or not admin_user.id:
            return {"error": "Admin não autorizado."}

        all_accessible_store_ids_for_admin = StoreAccessService.get_accessible_store_ids_with_fallback(db, admin_user)

        if requested_store_id not in all_accessible_store_ids_for_admin:
            return {'error': 'Acesso negado: Você não tem permissão para gerenciar esta loja.'}

        store = db.query(models.Store).filter_by(id=requested_store_id).first()
        if not store:
            return {"error": "Loja não encontrada."}

        config = db.query(models.StoreOperationConfig).filter_by(store_id=store.id).first()

        if not config:
            config = models.StoreOperationConfig(store_id=store.id)
            db.add(config)

        try:
            updatable_fields = [
                "is_store_open", "auto_accept_orders", "auto_print_orders",
                "main_printer_destination", "kitchen_printer_destination", "bar_printer_destination",
                "delivery_enabled", "delivery_estimated_min", "delivery_estimated_max",
                "delivery_fee", "delivery_min_order", "delivery_scope",
                "pickup_enabled", "pickup_estimated_min", "pickup_estimated_max",
                "pickup_instructions",
                "table_enabled", "table_estimated_min", "table_estimated_max",
                "table_instructions"
            ]

            for field in updatable_fields:
                if field in data:
                    setattr(config, field, data[field])

            db.commit()
            db.refresh(config)
            await emit_store_updates(db, requested_store_id)

        except Exception as e:
            db.rollback()
            print(f"❌ Erro CRÍTICO ao atualizar configuração da loja: {str(e)}")
            return {"error": str(e)}


# A versão antiga desta função está comentada para referência
# async def handle_join_store_room(self, sid, data): ...

# ✅ CORREÇÃO PRINCIPAL: A função agora aceita 'sio_namespace' como o primeiro argumento
async def handle_join_store_room(sio_namespace, sid, data):
    """
    Handler para quando o admin seleciona uma loja no frontend.
    Esta função agora tem logging detalhado para depuração.
    """
    store_id = data.get('store_id')
    if not store_id:
        print("⚠️ [join_store_room] Recebido sem store_id.")
        return

    print(f"🕵️‍♂️ [DEBUG] Iniciando processamento de 'join_store_room' para loja {store_id} (SID: {sid})")

    with get_db_manager() as db:
        try:
            # 1. Lógica de verificação de assinatura e acesso à sala
            store = db.query(models.Store).get(store_id)
            if not store:
                return {'status': 'error', 'message': 'Loja não encontrada.'}

            subscription_payload, is_blocked = SubscriptionService.get_subscription_details(store)
            if is_blocked:
                print(f"🔐 [join_store_room] Acesso bloqueado para SID {sid} à loja {store_id}.")
                await sio_namespace.emit('subscription_error',
                                         {'store_id': store_id, 'subscription': subscription_payload}, to=sid)
                return {'status': 'error', 'message': 'Acesso bloqueado devido à assinatura.'}

            session = SessionService.get_session(db, sid, client_type="admin")
            if not session:
                return {'status': 'error', 'message': 'Sessão inválida.'}

            if session.store_id and session.store_id != store_id:
                await sio_namespace.leave_room(sid, f"admin_store_{session.store_id}")

            await sio_namespace.enter_room(sid, f"admin_store_{store_id}")
            SessionService.update_session_store(db, sid=sid, store_id=store_id)
            print(f"✅ [DEBUG] Admin {sid} entrou na sala de socket da loja {store_id}.")

            # 2. INSTRUMENTAÇÃO PARA DEBUG
            emit_functions_to_run = {
                "store_updated": admin_emit_store_updated(db, store_id),
                "dashboard_data": admin_emit_dashboard_data_updated(db, store_id, sid),
                "payables_data": admin_emit_dashboard_payables_data_updated(db, store_id, sid),
                "orders_initial": admin_emit_orders_initial(db, store_id, sid),
                "tables_and_commands": admin_emit_tables_and_commands(db, store_id, sid),
                "products_updated": admin_emit_products_updated(db, store_id),
                "conversations_initial": admin_emit_conversations_initial(db, store_id, sid),
                "financials_updated": admin_emit_financials_updated(db, store_id, sid)
            }

            for name, coro in emit_functions_to_run.items():
                try:
                    print(f"⏳ [DEBUG] Executando emissor: '{name}'...")
                    await coro
                    print(f"✔️ [DEBUG] Emissor '{name}' concluído com sucesso.")
                except TypeError as e:
                    if "can't subtract offset-naive and offset-aware datetimes" in str(e):
                        print(f"🔥🔥🔥 [FANTASMA DO DATETIME ENCONTRADO] Erro ao executar o emissor '{name}' 🔥🔥🔥")
                        traceback.print_exc()
                        return
                    else:
                        raise
                except Exception as e:
                    print(f"🔥🔥🔥 [ERRO INESPERADO] Erro ao executar o emissor '{name}' 🔥🔥🔥")
                    traceback.print_exc()
                    return

            print(f"✅ [DEBUG] Todos os dados iniciais para a loja {store_id} foram emitidos com sucesso para {sid}.")
            return {'status': 'success', 'joined_room': f"admin_store_{store_id}"}

        except Exception as e:
            print(f"❌ [join_store_room] Erro GERAL ao processar para a loja {store_id}: {e}")
            traceback.print_exc()
            return {'status': 'error', 'message': 'Erro interno do servidor.'}


async def handle_leave_store_room(sio_namespace, sid, data):
    """
    Remove um admin da sala de uma loja específica.
    """
    try:
        store_id = data.get("store_id")
        if not store_id:
            return {'status': 'error', 'message': 'store_id é obrigatório'}

        with get_db_manager() as db:
            session = SessionService.get_session(db, sid, client_type="admin")

            if not session:
                return {'status': 'error', 'message': 'Sessão inválida.'}

            if session.store_id == store_id:
                room = f"admin_store_{store_id}"
                await sio_namespace.leave_room(sid, room)
                print(f"🚪 [leave_store_room] Admin {sid} saiu da sala: {room}")
                return {'status': 'success', 'left_room': room}
            else:
                print(
                    f"⚠️ [leave_store_room] Admin {sid} tentou sair da loja {store_id}, mas a loja ativa era {session.store_id}.")
                return {'status': 'error', 'message': 'Inconsistência de estado da loja.'}

    except Exception as e:
        print(f"❌ [leave_store_room] Erro ao processar para a loja {data.get('store_id')}: {e}")
        return {'status': 'error', 'message': 'Erro interno do servidor.'}