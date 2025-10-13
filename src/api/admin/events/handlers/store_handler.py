import asyncio
import traceback
from sqlalchemy import delete
from urllib.parse import parse_qs

from src.api.admin.services.store_access_service import StoreAccessService
from src.api.admin.services.store_session_service import SessionService
from src.api.admin.services.subscription_service import SubscriptionService
from src.api.admin.socketio import emitters
from src.api.admin.utils.authorize_admin import authorize_admin_by_jwt
from src.api.admin.utils.emit_updates import emit_store_updates

from src.core import models

from src.core.database import get_db_manager
from src.socketio_instance import sio


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


# ✅ REMOVIDO: A função handle_update_operation_config foi removida,
# pois a lógica agora está centralizada no endpoint HTTP PUT.


async def handle_join_store_room(sid, data):
    store_id = data.get('store_id')
    if not store_id:
        return

    await sio.enter_room(sid, f'admin_store_{store_id}', namespace='/admin')

    # ✅ CORREÇÃO: Usamos o 'get_db_manager' diretamente aqui.
    # A cada chamada, ele cria uma nova sessão de banco de dados, fresca e pronta para uso.
    with get_db_manager() as db:
        try:
            # Agora que o bug do dashboard foi corrigido na fonte, podemos
            # movê-lo de volta para a lista de confiança.
            emitters_to_run = [
                emitters.admin_emit_store_updated(db=db, store_id=store_id),
              #  emitters.admin_emit_dashboard_data_updated(db=db, store_id=store_id, sid=sid),
                emitters.admin_emit_dashboard_payables_data_updated(db=db, store_id=store_id, sid=sid),
                emitters.admin_emit_orders_initial(db=db, store_id=store_id, sid=sid),
                emitters.admin_emit_tables_and_commands(db=db, store_id=store_id, sid=sid),
                emitters.admin_emit_products_updated(db=db, store_id=store_id),
                emitters.emit_chatbot_config_update(db=db, store_id=store_id),
                emitters.admin_emit_conversations_initial(db=db, store_id=store_id, sid=sid),
                emitters.admin_emit_financials_updated(db=db, store_id=store_id, sid=sid)
            ]

            await asyncio.gather(*emitters_to_run, return_exceptions=True)

        except Exception as e:
            print(f"🔥🔥🔥 [ERRO GERAL] Erro no manipulador de join_store_room: {e}")
        # O 'with' statement já garante que 'db.close()' será chamado.

    print(f"🏁 [DEBUG] Todos os emissores para a loja {store_id} foram processados.")






async def handle_leave_store_room(sio_namespace, sid, data):
    """
    Remove um admin da sala de uma loja específica.
    ✅ CORREÇÃO: Remove a verificação de store_id da sessão
    """
    try:
        store_id = data.get("store_id")
        if not store_id:
            return {'status': 'error', 'message': 'store_id é obrigatório'}

        with get_db_manager() as db:
            session = SessionService.get_session(db, sid, client_type="admin")

            if not session:
                return {'status': 'error', 'message': 'Sessão inválida.'}

            # ✅ CORREÇÃO: Remove a verificação problemática
            # Permite sair de qualquer sala, independentemente do store_id da sessão
            room = f"admin_store_{store_id}"
            await sio_namespace.leave_room(sid, room)
            print(f"🚪 [leave_store_room] Admin {sid} saiu da sala: {room}")
            return {'status': 'success', 'left_room': room}

    except Exception as e:
        print(f"❌ [leave_store_room] Erro ao processar para a loja {data.get('store_id')}: {e}")
        return {'status': 'error', 'message': 'Erro interno do servidor.'}