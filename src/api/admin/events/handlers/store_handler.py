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


# Em: src/api/admin/handlers/store_handler.py

async def handle_set_consolidated_stores(self, sid, data):
    """
    Atualiza as PREFERÊNCIAS de lojas consolidadas de um admin no banco de dados.
    Esta função NÃO gerencia mais a entrada/saída de salas.
    """
    try:
        selected_store_ids = set(data.get("store_ids", []))
        if not isinstance(data.get("store_ids"), list):
            return {"error": "'store_ids' deve ser uma lista"}

        with get_db_manager() as db:
            session = SessionService.get_session(db, sid)
            if not session or not session.admin_id:
                return {"error": "Sessão não autorizada"}

            admin_id = session.admin_id

            # Deleta todas as seleções antigas do admin de uma vez
            db.execute(
                delete(models.AdminConsolidatedStoreSelection).where(
                    models.AdminConsolidatedStoreSelection.admin_id == admin_id
                )
            )

            # Adiciona as novas seleções
            # (Opcional: você pode validar se o admin tem acesso a estas lojas)
            for store_id in selected_store_ids:
                new_selection = models.AdminConsolidatedStoreSelection(
                    admin_id=admin_id, store_id=store_id
                )
                db.add(new_selection)

            db.commit()

            print(f"✅ Preferências de consolidação do admin {admin_id} atualizadas para: {selected_store_ids}")

            # Apenas notifica o cliente sobre a mudança na lista de IDs consolidados.
            # O cliente usará isso para atualizar a UI (ex: marcar/desmarcar checkboxes).
            await self.emit(
                "consolidated_stores_updated",
                {"store_ids": list(selected_store_ids)},
                to=sid,
            )

            return {"success": True, "selected_stores": list(selected_store_ids)}

    except Exception as e:
        # Garante o rollback em caso de erro na transação
        if 'db' in locals() and db.is_active:
            db.rollback()
        print(f"❌ Erro em on_set_consolidated_stores: {str(e)}")
        return {"error": f"Falha interna: {str(e)}"}


# async def handle_set_consolidated_stores(self, sid, data):
#     try:
#         selected_store_ids = data.get("store_ids", [])
#         if not isinstance(selected_store_ids, list):
#             print("❌ 'store_ids' deve ser uma lista em on_set_consolidated_stores")
#             return {"error": "'store_ids' deve ser uma lista"}
#
#         with get_db_manager() as db:
#
#             session = db.query(models.StoreSession).filter_by(sid=sid, client_type="admin").first()
#             if not session:
#                 print(f"❌ Sessão não encontrada para sid {sid} em on_set_consolidated_stores")
#                 return {"error": "Sessão não autorizada"}
#
#             query = parse_qs(self.environ[sid].get("QUERY_STRING", ""))
#             token = query.get("admin_token", [None])[0]
#             if not token:
#                 return {"error": "Token obrigatório para esta operação"}
#             totem_auth_user = await authorize_admin(db, token)
#             if not totem_auth_user or not totem_auth_user.id:
#                 return {"error": "Admin não autorizado"}
#
#             admin_id = totem_auth_user.id
#
#             # Busca todas as lojas às quais o admin tem acesso com a role 'admin'
#
#             all_accessible_store_ids_for_admin = StoreAccessService.get_accessible_store_ids_with_fallback(
#                 db, totem_auth_user
#             )
#
#             print(
#                 f"DEBUG: all_accessible_store_ids para admin {admin_id} (por machine_name): {all_accessible_store_ids_for_admin}")
#
#             # Fallback para adicionar a loja principal do usuário se não estiver nas acessíveis
#             if not all_accessible_store_ids_for_admin and totem_auth_user.store_id:
#                 all_accessible_store_ids_for_admin.append(totem_auth_user.store_id)
#                 print(
#                     f"DEBUG: Adicionada store_id do usuário autenticado como fallback: {totem_auth_user.store_id}")
#
#             # Recupera as seleções atuais do admin no DB
#             current_consolidated_selections = db.execute(
#                 select(models.AdminConsolidatedStoreSelection).where(
#                     models.AdminConsolidatedStoreSelection.admin_id == admin_id
#                 )
#             ).scalars().all()
#             current_consolidated_ids_in_db = {
#                 s.store_id for s in current_consolidated_selections
#             }
#
#             # Lojas para remover da seleção e das rooms
#             to_remove_ids = current_consolidated_ids_in_db - set(selected_store_ids)
#             for store_id_to_remove in to_remove_ids:
#                 room = f"admin_store_{store_id_to_remove}"
#                 await self.leave_room(sid, room)
#                 db.execute(
#                     delete(models.AdminConsolidatedStoreSelection).where(
#                         models.AdminConsolidatedStoreSelection.admin_id == admin_id,
#                         models.AdminConsolidatedStoreSelection.store_id == store_id_to_remove,
#                     )
#                 )
#                 print(
#                     f"🚪 Admin {sid} saiu da sala e removeu seleção da loja:"
#                     f" {store_id_to_remove}"
#                 )
#
#             # Lojas para adicionar à seleção e às rooms
#             to_add_ids = set(selected_store_ids) - current_consolidated_ids_in_db
#             for store_id_to_add in to_add_ids:
#                 # VALIDAÇÃO: Valide se o admin realmente tem acesso a esta loja
#                 if store_id_to_add not in all_accessible_store_ids_for_admin:
#                     print(
#                         f"⚠️ Admin {sid} tentou adicionar loja {store_id_to_add}"
#                         f" sem permissão."
#                     )
#                     continue
#
#                 room = f"admin_store_{store_id_to_add}"
#                 await self.enter_room(sid, room)
#                 try:
#                     new_selection = models.AdminConsolidatedStoreSelection(
#                         admin_id=admin_id, store_id=store_id_to_add
#                     )
#                     db.add(new_selection)
#                     db.commit()
#                     print(
#                         f"✅ Admin {sid} entrou na sala e adicionou seleção da loja:"
#                         f" {store_id_to_add}"
#                     )
#                     await self._emit_initial_data(db, store_id_to_add, sid)
#                 except IntegrityError:
#                     db.rollback()
#                     print(
#                         f"⚠️ Seleção de loja {store_id_to_add} já existia para admin"
#                         f" {admin_id}."
#                     )
#                     await self.enter_room(sid, room)
#                 except Exception as add_e:
#                     db.rollback()
#                     print(
#                         f"❌ Erro ao adicionar seleção da loja {store_id_to_add}:"
#                         f" {str(add_e)}"
#                     )
#
#             # Emitir a nova lista de lojas consolidadas para o frontend
#             updated_consolidated_ids = list(db.execute(
#                 select(models.AdminConsolidatedStoreSelection.store_id).where(
#                     models.AdminConsolidatedStoreSelection.admin_id == admin_id
#                 )
#             ).scalars())
#
#             await self.emit(
#                 "consolidated_stores_updated",
#                 {"store_ids": updated_consolidated_ids},
#                 to=sid,
#             )
#             print(
#                 f"✅ Seleção consolidada atualizada para {sid}:"
#                 f" {updated_consolidated_ids}"
#             )
#
#             return {"success": True, "selected_stores": updated_consolidated_ids}
#
#     except Exception as e:
#         db.rollback()
#         print(f"❌ Erro em on_set_consolidated_stores: {str(e)}")
#         return {"error": f"Falha interna: {str(e)}"}

#
# async def handle_join_store_room(self, sid, data):
#     try:
#         store_id = data.get("store_id")
#         if not store_id:
#             print("❌ store_id ausente em join_store_room")
#             return
#
#         with get_db_manager() as db:
#
#             session = SessionService.get_session(db, sid, client_type="admin")
#
#             if not session:
#                 print(f"❌ Sessão não encontrada para sid {sid} para join_store_room")
#                 return
#
#
#             if session.store_id and session.store_id != store_id:
#                 old_room = f"admin_store_{session.store_id}"
#                 await self.leave_room(sid, old_room)
#                 print(f"🚪 Admin {sid} saiu da sala antiga: {old_room}")
#
#             new_room = f"admin_store_{store_id}"
#             await self.enter_room(sid, new_room)
#             print(f"✅ Admin {sid} entrou na sala dinâmica: {new_room}")
#
#
#             SessionService.create_or_update_session(db, sid, store_id, client_type="admin")
#
#
#             await self._emit_initial_data(db, store_id, sid)
#
#     except Exception as e:
#         print(f"❌ Erro ao entrar na sala da loja {store_id}: {e}")


# async def handle_leave_store_room(self, sid, data):
#     try:
#         store_id = data.get("store_id")
#         if not store_id:
#             print("❌ store_id ausente em leave_store_room")
#             return
#
#         with get_db_manager() as db:
#             session = SessionService.get_session(db, sid, client_type="admin")
#
#             if not session:
#                 print(f"❌ Sessão não encontrada para sid {sid} para leave_store_room")
#                 return
#
#             if session.store_id == store_id:
#                 room = f"admin_store_{store_id}"
#                 await self.leave_room(sid, room)
#                 print(f"🚪 Admin {sid} saiu da sala: {room}")
#             else:
#                 print(f"⚠️ Admin {sid} tentou sair da loja {store_id}, mas a loja ativa era {session.store_id}.")
#     except Exception as e:
#         print(f"❌ Erro ao sair da sala da loja {store_id}: {e}")


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


# O nome do método deve ser o padrão da biblioteca para ser chamado
# pelo evento 'join_store_room' emitido pelo Flutter.
async def handle_join_store_room(self, sid, data):
    """
    Inscreve um admin na sala de uma loja específica para receber dados detalhados.
    Este evento é chamado pelo cliente quando o usuário troca de loja na UI.
    """
    try:
        store_id = data.get("store_id")
        if not store_id:
            print(f"❌ [join_store_room] sid {sid} enviou um pedido sem store_id.")
            # É uma boa prática retornar um erro para o cliente saber o que aconteceu.
            return {'status': 'error', 'message': 'store_id é obrigatório'}

        with get_db_manager() as db:
            # Busca a sessão atual do admin para saber em qual sala ele está.
            session = SessionService.get_session(db, sid, client_type="admin")

            if not session:
                print(f"❌ [join_store_room] Sessão não encontrada para sid {sid}.")
                return {'status': 'error', 'message': 'Sessão inválida.'}

            # Se o admin já estava ouvindo outra loja, remove ele da sala antiga.
            # Isso evita que ele continue recebendo dados de uma loja que não está mais vendo.
            if session.store_id and session.store_id != store_id:
                old_room = f"admin_store_{session.store_id}"
                await self.leave_room(sid, old_room)
                print(f"🚪 [join_store_room] Admin {sid} saiu da sala antiga: {old_room}")

            # Entra na nova sala para começar a receber os dados da loja selecionada.
            new_room = f"admin_store_{store_id}"
            await self.enter_room(sid, new_room)
            print(f"✅ [join_store_room] Admin {sid} entrou na sala dinâmica: {new_room}")

            # Atualiza a sessão no banco de dados para registrar qual loja está ativa.
            SessionService.create_or_update_session(db, sid, store_id, client_type="admin")

            # Envia a carga inicial de dados (pedidos, produtos, etc.) para a nova sala.
            await self._emit_initial_data(db, store_id, sid)

            # Retorna sucesso para o cliente.
            return {'status': 'success', 'joined_room': new_room}

    except Exception as e:
        print(f"❌ [join_store_room] Erro ao processar para a loja {data.get('store_id')}: {e}")
        # Informa o cliente que algo deu errado no servidor.
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