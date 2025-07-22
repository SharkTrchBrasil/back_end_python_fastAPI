from sqlalchemy.exc import IntegrityError
from sqlalchemy import select, delete
from urllib.parse import parse_qs
from src.api.admin.schemas.store_settings import StoreSettingsBase
from src.api.admin.services.store_access_service import StoreAccessService
from src.api.admin.services.store_session_service import SessionService
from src.core import models
from src.api.admin.socketio.emitters import (

    admin_emit_store_full_updated,

    admin_emit_store_updated,
)
from src.api.admin.utils.authorize_admin import authorize_admin
from src.core.database import get_db_manager


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

            # ✨ CORREÇÃO AQUI: Verificamos 'user_id'
            if not session or not session.user_id:
                return {"error": "Sessão não autorizada"}

            # ✨ E AQUI: Usamos 'user_id'
            admin_id = session.user_id

            # Deleta todas as seleções antigas do admin de uma vez
            db.execute(
                delete(models.AdminConsolidatedStoreSelection).where(
                    models.AdminConsolidatedStoreSelection.admin_id == admin_id
                )
            )

            # Adiciona as novas seleções
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

async def handle_update_store_settings(self, sid, data):
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

        totem_auth_user = await authorize_admin(db, admin_token)
        if not totem_auth_user or not totem_auth_user.id:
            return {"error": "Admin não autorizado."}

        admin_id = totem_auth_user.id

        # *** CORREÇÃO APLICADA AQUI: Adicionar a lógica de busca de lojas acessíveis ***
        all_accessible_store_ids_for_admin = StoreAccessService.get_accessible_store_ids_with_fallback(db,
                                                                                                       totem_auth_user)

        # Fallback para adicionar a loja principal do usuário se não estiver nas acessíveis
        if not all_accessible_store_ids_for_admin and totem_auth_user.store_id:
            all_accessible_store_ids_for_admin.append(totem_auth_user.store_id)

        if requested_store_id not in all_accessible_store_ids_for_admin:
            return {'error': 'Acesso negado: Você não tem permissão para gerenciar esta loja.'}

        store = db.query(models.Store).filter_by(id=requested_store_id).first()
        if not store:
            return {"error": "Loja não encontrada."}

        settings = db.query(models.StoreSettings).filter_by(store_id=store.id).first()
        if not settings:
            return {"error": "Configurações não encontradas para esta loja."}

        try:
            for field in [
                "is_delivery_active", "is_takeout_active", "is_table_service_active",
                "is_store_open", "auto_accept_orders", "auto_print_orders"
            ]:
                if field in data:
                    setattr(settings, field, data[field])

            db.commit()
            db.refresh(settings)
            db.refresh(store)  # Refresh na store para garantir que as configurações sejam atualizadas ao emitir

            await admin_emit_store_updated(store)
            await admin_emit_store_full_updated(db, store.id)

            return StoreSettingsBase.model_validate(settings).model_dump(mode='json')

        except Exception as e:
            db.rollback()
            print(f"❌ Erro ao atualizar configurações da loja: {str(e)}")
            return {"error": str(e)}


async def handle_join_store_room(self, sid, data):
    """
    Inscreve um admin na sala de uma loja específica para receber dados detalhados.
    Este evento é chamado pelo cliente quando o usuário troca de loja na UI.
    """
    try:
        store_id = data.get("store_id")
        if not store_id:
            print(f"❌ [join_store_room] sid {sid} enviou um pedido sem store_id.")
            return {'status': 'error', 'message': 'store_id é obrigatório'}

        with get_db_manager() as db:
            session = SessionService.get_session(db, sid, client_type="admin")

            if not session:
                print(f"❌ [join_store_room] Sessão não encontrada para sid {sid}.")
                return {'status': 'error', 'message': 'Sessão inválida.'}

            if session.store_id and session.store_id != store_id:
                old_room = f"admin_store_{session.store_id}"
                await self.leave_room(sid, old_room)
                print(f"🚪 [join_store_room] Admin {sid} saiu da sala antiga: {old_room}")

            new_room = f"admin_store_{store_id}"
            await self.enter_room(sid, new_room)
            print(f"✅ [join_store_room] Admin {sid} entrou na sala dinâmica: {new_room}")

            # ✨ CORREÇÃO APLICADA AQUI ✨
            # Usamos o novo método, mais simples e específico para esta tarefa.
            # Ele apenas atualiza o store_id da sessão existente.
            SessionService.update_session_store(db, sid=sid, store_id=store_id)

            # Envia a carga inicial de dados (pedidos, produtos, etc.) para a nova sala.
            await self._emit_initial_data(db, store_id, sid)

            return {'status': 'success', 'joined_room': new_room}

    except Exception as e:
        print(f"❌ [join_store_room] Erro ao processar para a loja {data.get('store_id')}: {e}")
        return {'status': 'error', 'message': 'Erro interno do servidor.'}



async def handle_leave_store_room(self, sid, data):
    """
    Remove um admin da sala de uma loja específica.
    Usa a lógica segura da versão original com o feedback da segunda versão.
    """
    try:
        store_id = data.get("store_id")
        if not store_id:
            print(f"❌ [leave_store_room] sid {sid} enviou um pedido sem store_id.")
            return {'status': 'error', 'message': 'store_id é obrigatório'}

        with get_db_manager() as db:
            session = SessionService.get_session(db, sid, client_type="admin")

            if not session:
                print(f"❌ [leave_store_room] Sessão não encontrada para sid {sid}.")
                return {'status': 'error', 'message': 'Sessão inválida.'}

            # Verifica se a loja que o cliente quer sair é a mesma que o servidor tem registrada.
            if session.store_id == store_id:
                room = f"admin_store_{store_id}"
                await self.leave_room(sid, room)
                print(f"🚪 [leave_store_room] Admin {sid} saiu da sala: {room}")
                return {'status': 'success', 'left_room': room}
            else:
                # Informa o cliente e o log do servidor sobre a inconsistência.
                print(f"⚠️ [leave_store_room] Admin {sid} tentou sair da loja {store_id}, mas a loja ativa era {session.store_id}.")
                return {'status': 'error', 'message': 'Inconsistência de estado da loja.'}

    except Exception as e:
        print(f"❌ [leave_store_room] Erro ao processar para a loja {data.get('store_id')}: {e}")
        return {'status': 'error', 'message': 'Erro interno do servidor.'}