import asyncio

from sqlalchemy import delete
from urllib.parse import parse_qs

from src.api.admin.services.store_access_service import StoreAccessService
from src.api.admin.services.store_session_service import SessionService
from src.api.admin.utils.authorize_admin import authorize_admin_by_jwt
from src.api.admin.utils.emit_updates import emit_store_updates
from src.api.crud.store_crud import get_store_base_details
from src.api.schemas.store.store_details import StoreDetails
from src.api.schemas.store.store_operation_config import StoreOperationConfigBase
from src.core import models
from src.api.admin.socketio.emitters import (
    admin_emit_store_updated, admin_emit_dashboard_data_updated,
    admin_emit_orders_initial, admin_emit_tables_and_commands, admin_emit_products_updated,
    admin_emit_financials_updated, admin_emit_dashboard_payables_data_updated,

)
from src.core.database import get_db_manager
from src.core.models import StoreOperationConfig


async def handle_set_consolidated_stores(self, sid, data):
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

            await self.emit(
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


async def handle_update_operation_config(self, sid, data):
    with get_db_manager() as db:
        session = SessionService.get_session(db, sid, client_type="admin")

        if not session:
            return {'error': 'Sessão não encontrada ou não autorizada'}

        requested_store_id = data.get("store_id")
        if not requested_store_id:
            return {'error': 'ID da loja é obrigatório para atualizar configurações.'}

        query_params = parse_qs(self.environ[sid].get("QUERY_STRING", ""))
        admin_token = query_params.get("admin_token", [None])[0]
        if not admin_token:
            return {"error": "Token de admin não encontrado na sessão."}

        # ✅ CORREÇÃO 1: Renomeado para clareza.
        admin_user = await authorize_admin_by_jwt(db, admin_token)
        if not admin_user or not admin_user.id:
            return {"error": "Admin não autorizado."}

        # A fonte de verdade para as lojas acessíveis.
        all_accessible_store_ids_for_admin = StoreAccessService.get_accessible_store_ids_with_fallback(db,
                                                                                                       admin_user)

        if requested_store_id not in all_accessible_store_ids_for_admin:
            return {'error': 'Acesso negado: Você não tem permissão para gerenciar esta loja.'}

        store = db.query(models.Store).filter_by(id=requested_store_id).first()
        if not store:
            return {"error": "Loja não encontrada."}

        # --- ✅ 2. LÓGICA ATUALIZADA PARA USAR 'StoreOperationConfig' ---
        config = db.query(models.StoreOperationConfig).filter_by(store_id=store.id).first()

        # Se não houver configuração, cria uma padrão em vez de retornar erro
        if not config:
            config = models.StoreOperationConfig(store_id=store.id)
            db.add(config)

        try:
            # ✅ CORREÇÃO: Lista explícita de campos atualizáveis.
            # Isso evita o erro no editor e torna a intenção do código mais clara.
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

            db.commit()  # Salva as alterações no banco de dados
            db.refresh()

            await emit_store_updates(store, requested_store_id)

        except Exception as e:
            db.rollback()
            print(f"❌ Erro ao atualizar configuração de operação da loja: {str(e)}")
            return {"error": str(e)}




async def handle_join_store_room(self, sid, data):
    """
    Inscreve um admin na sala da loja e envia todos os dados iniciais de forma granular.
    """
    try:
        store_id = data.get("store_id")
        if not store_id:
            return {'status': 'error', 'message': 'store_id é obrigatório'}

        with get_db_manager() as db:
            session = SessionService.get_session(db, sid, client_type="admin")
            if not session:
                return {'status': 'error', 'message': 'Sessão inválida.'}

            # Lógica para sair da sala antiga (seu código está perfeito)
            if session.store_id and session.store_id != store_id:
                old_room = f"admin_store_{session.store_id}"
                await self.leave_room(sid, old_room)
                print(f"🚪 [join_store_room] Admin {sid} saiu da sala antiga: {old_room}")

            # Entra na nova sala
            new_room = f"admin_store_{store_id}"
            await self.enter_room(sid, new_room)
            print(f"✅ [join_store_room] Admin {sid} entrou na sala dinâmica: {new_room}")
            SessionService.update_session_store(db, sid=sid, store_id=store_id)


            await asyncio.gather(
                admin_emit_store_updated(db, store_id),
                admin_emit_dashboard_data_updated(db, store_id, sid),
                admin_emit_dashboard_payables_data_updated(db, store_id, sid),
                admin_emit_financials_updated(db, store_id, sid),
                admin_emit_orders_initial(db, store_id, sid),
                admin_emit_tables_and_commands(db, store_id, sid),
                admin_emit_products_updated(db, store_id)
            )
            print(f"✅ [Socket] Pacote de dados iniciais enviado para loja {store_id}.")

            return {'status': 'success', 'joined_room': new_room}

    except Exception as e:
        print(f"❌ [join_store_room] Erro ao processar para a loja {data.get('store_id')}: {e}")
        return {'status': 'error', 'message': 'Erro interno do servidor.'}





async def handle_leave_store_room(self, sid, data):
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
                await self.leave_room(sid, room)
                print(f"🚪 [leave_store_room] Admin {sid} saiu da sala: {room}")
                return {'status': 'success', 'left_room': room}
            else:
                print(f"⚠️ [leave_store_room] Admin {sid} tentou sair da loja {store_id}, mas a loja ativa era {session.store_id}.")
                return {'status': 'error', 'message': 'Inconsistência de estado da loja.'}

    except Exception as e:
        print(f"❌ [leave_store_room] Erro ao processar para a loja {data.get('store_id')}: {e}")
        return {'status': 'error', 'message': 'Erro interno do servidor.'}

