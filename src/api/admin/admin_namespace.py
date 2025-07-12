from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import joinedload
from sqlalchemy import select, delete
from datetime import datetime
from urllib.parse import parse_qs
from socketio import AsyncNamespace
from src.api.admin.schemas.store_settings import StoreSettingsBase
from src.api.app.events.socketio_emitters import emit_store_updated
from src.core import models
from src.api.admin.events.admin_socketio_emitters import (
    admin_emit_orders_initial,
    admin_product_list_all,
    admin_emit_store_full_updated,
    admin_emit_order_updated_from_obj,
    admin_emit_store_updated,
)
from src.api.admin.services.authorize_admin import authorize_admin
from src.core.database import get_db_manager






class AdminNamespace(AsyncNamespace):
    async def on_connect(self, sid, environ):
        print(f"[ADMIN] Conexão estabelecida: {sid}")
        query = parse_qs(environ.get("QUERY_STRING", ""))
        token = query.get("admin_token", [None])[0]

        if not token:
            raise ConnectionRefusedError("Token obrigatório")

        with get_db_manager() as db:
            try:
                # Use joinedload para buscar as lojas do admin e evitar N+1 queries
                totem_auth = await authorize_admin(db, token)
                if not totem_auth or not totem_auth.store_id or not totem_auth.id:
                    print(f"⚠️ Admin {sid} conectado, mas sem lojas ou admin_id.")
                    raise ConnectionRefusedError(
                        "Acesso negado: Nenhuma loja associada ou admin inválido."
                    )

                # Recupera as lojas que o admin selecionou para consolidação
                # Usamos totem_auth.id para buscar as seleções
                consolidated_store_ids = [
                    s.store_id
                    for s in db.execute(
                        select(models.AdminConsolidatedStoreSelection.store_id).where(
                            models.AdminConsolidatedStoreSelection.admin_id == totem_auth.id
                        )
                    ).scalars()
                ]

                # Se não houver lojas selecionadas para consolidação, por padrão, selecione a loja do admin
                if not consolidated_store_ids:
                    consolidated_store_ids.append(totem_auth.store_id)

                # Criar/atualizar sessão na tabela store_sessions
                # A store_id na sessão agora pode representar a "loja ativa principal" ou a primeira da lista consolidada
                # Mas para o propósito de rooms, vamos gerenciar via loop abaixo.
                session = db.query(models.StoreSession).filter_by(sid=sid).first()
                if not session:
                    session = models.StoreSession(
                        sid=sid,
                        store_id=consolidated_store_ids[0]
                        if consolidated_store_ids
                        else None,  # Defina a primeira loja da consolidação como ativa inicial
                        client_type="admin",
                    )
                    db.add(session)
                else:
                    session.store_id = (
                        consolidated_store_ids[0] if consolidated_store_ids else None
                    )
                    session.client_type = "admin"
                    session.updated_at = datetime.utcnow()

                db.commit()
                print(
                    f"✅ Session criada/atualizada para sid {sid} com lojas consolidadas:"
                    f" {consolidated_store_ids}"
                )

                # Fazer o SID entrar nas rooms de TODAS as lojas consolidadas
                for store_id_to_join in consolidated_store_ids:
                    room = f"admin_store_{store_id_to_join}"
                    await self.enter_room(sid, room)
                    print(f"✅ Admin {sid} entrou na room para consolidação: {room}")
                    # Opcional: Emitir dados iniciais para CADA UMA das lojas consolidadas para este SID
                    # Isso garante que o frontend receba os dados de todas elas.
                    # Você precisará ajustar _emit_initial_data para ser chamado várias vezes.
                    # Ou o frontend fará uma requisição para dados consolidados.
                    # Para manter o fluxo atual, vamos emitir para cada uma:
                    await self._emit_initial_data(db, store_id_to_join, sid)

                # Enviar a lista COMPLETA de lojas que o admin tem acesso (para o seletor)
                # e quais estão ativas para consolidação
                # Assuming totem_auth.store is the main store, and you don't have a list of stores.
                stores_list_data = [{
                    "id": totem_auth.store_id,  # Use totem_auth.store_id
                    "name": totem_auth.store.name,  # Use totem_auth.store.name
                    "is_consolidated": totem_auth.store_id in consolidated_store_ids,  # Verifique using totem_auth.store_id
                }]
                await self.emit("admin_stores_list", {"stores": stores_list_data}, to=sid)
                print(f"✅ Lista de lojas e seleção consolidada enviada para {sid}")

            except Exception as e:
                db.rollback()
                print(f"❌ Erro na conexão: {str(e)}")
                raise

    async def on_disconnect(self, sid):
        print(f"[ADMIN] Desconexão: {sid}")
        with get_db_manager() as db:
            try:
                session = db.query(models.StoreSession).filter_by(sid=sid).first()
                if session:
                    # Recuperar TODAS as lojas que este admin poderia ter selecionado para consolidação
                    # Isso é importante porque a sessão.store_id pode ser apenas UMA loja.
                    # Você precisará do admin_id para isso.
                    # Ou, uma abordagem mais simples: o socketio automaticamente remove o sid de todas as rooms ao desconectar.
                    # No entanto, se você quiser ser explícito ou ter lógica adicional, precisaria do admin_id.

                    # Para o propósito imediato, o Socket.IO já faz a limpeza das rooms automaticamente na desconexão.
                    # Podemos simplesmente remover a sessão do DB.
                    db.delete(session)
                    db.commit()
                    print(f"✅ Session removida para sid {sid}")
            except Exception as e:
                print(f"❌ Erro na desconexão: {str(e)}")
                db.rollback()

    async def on_set_consolidated_stores(self, sid, data):
        try:
            selected_store_ids = data.get("store_ids", [])
            if not isinstance(selected_store_ids, list):
                print("❌ 'store_ids' deve ser uma lista em on_set_consolidated_stores")
                return {"error": "'store_ids' deve ser uma lista"}

            with get_db_manager() as db:
                session = db.query(models.StoreSession).filter_by(sid=sid, client_type="admin").first()
                if not session:
                    print(f"❌ Sessão não encontrada para sid {sid} em on_set_consolidated_stores")
                    return {"error": "Sessão não autorizada"}

                # Você precisará do admin_id.  Para simplificar, vamos recuperá-lo via token novamente.
                query = parse_qs(self.environ[sid].get("QUERY_STRING", ""))  # 'self.environ[sid]' acessa o environ da conexão
                token = query.get("admin_token", [None])[0]
                if not token:
                    return {"error": "Token obrigatório para esta operação"}
                totem_auth = await authorize_admin(db, token)
                if not totem_auth or not totem_auth.id:
                    return {"error": "Admin não autorizado"}

                admin_id = totem_auth.id

                # Recupera as seleções atuais do admin no DB
                current_consolidated_selections = db.execute(
                    select(models.AdminConsolidatedStoreSelection).where(
                        models.AdminConsolidatedStoreSelection.admin_id == admin_id
                    )
                ).scalars().all()
                current_consolidated_ids_in_db = {
                    s.store_id for s in current_consolidated_selections
                }

                # Lojas para remover da seleção e das rooms
                to_remove_ids = current_consolidated_ids_in_db - set(selected_store_ids)
                for store_id_to_remove in to_remove_ids:
                    room = f"admin_store_{store_id_to_remove}"
                    await self.leave_room(sid, room)
                    db.execute(
                        delete(models.AdminConsolidatedStoreSelection).where(
                            models.AdminConsolidatedStoreSelection.admin_id == admin_id,
                            models.AdminConsolidatedStoreSelection.store_id == store_id_to_remove,
                        )
                    )
                    print(
                        f"🚪 Admin {sid} saiu da sala e removeu seleção da loja:"
                        f" {store_id_to_remove}"
                    )

                # Lojas para adicionar à seleção e às rooms
                to_add_ids = set(selected_store_ids) - current_consolidated_ids_in_db
                for store_id_to_add in to_add_ids:
                    # Valide se o admin realmente tem acesso a esta loja
                    if store_id_to_add != totem_auth.store_id:  # Use totem_auth.store_id
                        print(
                            f"⚠️ Admin {sid} tentou adicionar loja {store_id_to_add}"
                            f" sem permissão."
                        )
                        continue  # Pula esta loja

                    room = f"admin_store_{store_id_to_add}"
                    await self.enter_room(sid, room)
                    try:
                        new_selection = models.AdminConsolidatedStoreSelection(
                            admin_id=admin_id, store_id=store_id_to_add
                        )
                        db.add(new_selection)
                        db.commit()  # Commit individual para capturar IntegrityError imediatamente
                        print(
                            f"✅ Admin {sid} entrou na sala e adicionou seleção da loja:"
                            f" {store_id_to_add}"
                        )
                        # Opcional: Emitir dados iniciais para a loja recém-adicionada
                        await self._emit_initial_data(db, store_id_to_add, sid)
                    except IntegrityError:
                        db.rollback()  # Rollback da transação atual para a falha específica
                        print(
                            f"⚠️ Seleção de loja {store_id_to_add} já existia para admin"
                            f" {admin_id}."
                        )
                        # Se já existia, podemos apenas garantir que ele esteja na room
                        await self.enter_room(sid, room)
                    except Exception as add_e:
                        db.rollback()
                        print(
                            f"❌ Erro ao adicionar seleção da loja {store_id_to_add}:"
                            f" {str(add_e)}"
                        )

                # Emitir a nova lista de lojas consolidadas para o frontend
                # para que ele possa atualizar o estado.
                updated_consolidated_ids = [
                    s.store_id
                    for s in db.execute(
                        select(models.AdminConsolidatedStoreSelection.store_id).where(
                            models.AdminConsolidatedStoreSelection.admin_id == admin_id
                        )
                    ).scalars()
                ]
                await self.emit(
                    "consolidated_stores_updated",
                    {"store_ids": updated_consolidated_ids},
                    to=sid,
                )
                print(
                    f"✅ Seleção consolidada atualizada para {sid}:"
                    f" {updated_consolidated_ids}"
                )

                return {"success": True, "selected_stores": updated_consolidated_ids}

        except Exception as e:
            db.rollback()
            print(f"❌ Erro em on_set_consolidated_stores: {str(e)}")
            return {"error": f"Falha interna: {str(e)}"}

    async def _emit_initial_data(self, db, store_id, sid):
        await admin_emit_store_full_updated(db, store_id, sid)
        await admin_product_list_all(db, store_id, sid)
        await admin_emit_orders_initial(db, store_id, sid)






    async def on_join_store_room(self, sid, data):
        try:
            store_id = data.get("store_id")
            if not store_id:
                print("❌ store_id ausente em join_store_room")
                return

            with get_db_manager() as db:
                session = db.query(models.StoreSession).filter_by(sid=sid, client_type='admin').first()
                if not session:
                    print(f"❌ Sessão não encontrada para sid {sid} para join_store_room")
                    return

                # ** CHAVE: Sair da sala antiga antes de entrar na nova **
                if session.store_id and session.store_id != store_id:
                    old_room = f"admin_store_{session.store_id}"
                    await self.leave_room(sid, old_room)
                    print(f"🚪 Admin {sid} saiu da sala antiga: {old_room}")

                # Entrar na nova sala
                new_room = f"admin_store_{store_id}"
                await self.enter_room(sid, new_room)
                print(f"✅ Admin {sid} entrou na sala dinâmica: {new_room}")

                # Atualizar a loja ativa na sessão
                session.store_id = store_id
                db.commit()
                db.refresh(session) # Opcional, para garantir que o objeto está atualizado

                # Emitir dados iniciais para o SID para a NOVA loja
                await self._emit_initial_data(db, store_id, sid)

        except Exception as e:
            print(f"❌ Erro ao entrar na sala da loja {store_id}: {e}")


    async def on_leave_store_room(self, sid, data):
        try:
            store_id = data.get("store_id")
            if not store_id:
                print("❌ store_id ausente em leave_store_room")
                return

            with get_db_manager() as db:
                session = db.query(models.StoreSession).filter_by(sid=sid, client_type='admin').first()
                if not session:
                    print(f"❌ Sessão não encontrada para sid {sid} para leave_store_room")
                    return

                # Apenas saia da sala se o store_id fornecido for o ativo
                if session.store_id == store_id:
                    room = f"admin_store_{store_id}"
                    await self.leave_room(sid, room)
                    print(f"🚪 Admin {sid} saiu da sala: {room}")
                    # Você pode opcionalmente limpar session.store_id aqui ou definir como None
                    # session.store_id = None
                    # db.commit()
                else:
                    print(f"⚠️ Admin {sid} tentou sair da loja {store_id}, mas a loja ativa era {session.store_id}.")
        except Exception as e:
            print(f"❌ Erro ao sair da sala da loja {store_id}: {e}")



    async def on_update_order_status(self, sid, data):
        with get_db_manager() as db:
            try:
                # 1. Validação básica dos dados de entrada
                if not all(key in data for key in ['order_id', 'new_status']):
                    return {'error': 'Dados incompletos'}

                # 2. Verifica a sessão (admin OU totem)
                session = db.query(models.StoreSession).filter_by(sid=sid).first()
                if not session:
                    return {'error': 'Sessão não autorizada'}

                # 3. Busca o pedido vinculado à LOJA da sessão
                order = db.query(models.Order).filter_by(
                    id=data['order_id'],
                    store_id=session.store_id
                ).first()

                if not order:
                    return {'error': 'Pedido não encontrado nesta loja'}

                # 4. Valida o novo status (exemplo com enum)
                valid_statuses = ['pending', 'preparing', 'ready', 'delivered']
                if data['new_status'] not in valid_statuses:
                    return {'error': 'Status inválido'}

                # 5. Atualização segura
                order.order_status = data['new_status']
                db.commit()
                db.refresh(order)

                # 6. Notificação
                await admin_emit_order_updated_from_obj(order)
                print(f"✅ [Session {sid}] Pedido {order.id} atualizado para: {data['new_status']}")

                return {'success': True, 'order_id': order.id, 'new_status': order.order_status}

            except Exception as e:
                db.rollback()
                print(f"❌ Erro ao atualizar pedido: {str(e)}")
                return {'error': 'Falha interna'}

    async def on_update_store_settings(self, sid, data):
        with get_db_manager() as db:
            # Agora verificamos a sessão em vez do totem diretamente
            session = db.query(models.StoreSession).filter_by(sid=sid, client_type='admin').first()
            if not session:
                return {'error': 'Sessão não encontrada ou não autorizada'}

            store = db.query(models.Store).filter_by(id=session.store_id).first()
            if not store:
                return {"error": "Loja associada não encontrada"}

            settings = db.query(models.StoreSettings).filter_by(store_id=store.id).first()
            if not settings:
                return {"error": "Configurações não encontradas"}

            try:
                for field in [
                    "is_delivery_active", "is_takeout_active", "is_table_service_active",
                    "is_store_open", "auto_accept_orders", "auto_print_orders"
                ]:
                    if field in data:
                        setattr(settings, field, data[field])

                db.commit()
                db.refresh(settings)
                db.refresh(store)

                await admin_emit_store_updated(store)
                await admin_emit_store_full_updated(db, store.id)

                return StoreSettingsBase.model_validate(settings).model_dump(mode='json')

            except Exception as e:
                db.rollback()
                print(f"❌ Erro ao atualizar configurações da loja: {str(e)}")
                return {"error": str(e)}























#
# class AdminNamespace(AsyncNamespace):
#     async def on_connect(self, sid, environ):
#         print(f"[ADMIN] Conexão estabelecida: {sid}")
#         query = parse_qs(environ.get('QUERY_STRING', ''))
#         token = query.get('admin_token', [None])[0]
#
#         if not token:
#             raise ConnectionRefusedError("Token obrigatório")
#
#         with get_db_manager() as db:
#             try:
#                 totem = await authorize_admin(db, token)
#                 if not totem or not totem.store:
#                     raise ConnectionRefusedError("Acesso negado")
#
#                 # Criar/atualizar sessão na tabela store_sessions
#                 session = db.query(models.StoreSession).filter_by(sid=sid).first()
#                 if not session:
#                     session = models.StoreSession(
#                         sid=sid,
#                         store_id=totem.store.id,
#                         client_type='admin'
#                     )
#                     db.add(session)
#                 else:
#                     session.store_id = totem.store.id
#                     session.client_type = 'admin'
#                     session.updated_at = datetime.utcnow()
#
#                 db.commit()
#                 print(f"✅ Session criada/atualizada para sid {sid}")
#
#                 for store in totem.stores:
#                     room = f"admin_store_{store.id}"
#                     await self.enter_room(sid, room)
#                     print(f"✅ Admin entrou na room: {room}")
#                     await self._emit_initial_data(db, store.id, sid)
#
#                 db.commit()
#
#             except Exception as e:
#                 db.rollback()
#                 print(f"❌ Erro na conexão: {str(e)}")
#                 raise
#
#     async def on_disconnect(self, sid):
#         print(f"[ADMIN] Desconexão: {sid}")
#         with get_db_manager() as db:
#             try:
#                 # Remover a sessão ao desconectar
#                 session = db.query(models.StoreSession).filter_by(sid=sid).first()
#                 if session:
#                     await self.leave_room(sid, f"admin_store_{session.store_id}")
#                     db.delete(session)
#                     db.commit()
#                     print(f"✅ Session removida para sid {sid}")
#
#                 # Opcional: também limpar o sid do totem (se ainda estiver usando)
#                 totem = db.query(models.TotemAuthorization).filter_by(sid=sid).first()
#                 if totem:
#                     totem.sid = None
#                     db.commit()
#             except Exception as e:
#                 print(f"❌ Erro na desconexão: {str(e)}")
#                 db.rollback()
#
#
#
#
#     async def _emit_initial_data(self, db, store_id, sid):
#         await admin_emit_store_full_updated(db, store_id, sid)
#         await admin_product_list_all(db, store_id, sid)
#         await admin_emit_orders_initial(db, store_id, sid)
#
#     async def on_update_order_status(self, sid, data):
#         with get_db_manager() as db:
#             try:
#                 # 1. Validação básica dos dados de entrada
#                 if not all(key in data for key in ['order_id', 'new_status']):
#                     return {'error': 'Dados incompletos'}
#
#                 # 2. Verifica a sessão (admin OU totem)
#                 session = db.query(models.StoreSession).filter_by(sid=sid).first()
#                 if not session:
#                     return {'error': 'Sessão não autorizada'}
#
#                 # 3. Busca o pedido vinculado à LOJA da sessão
#                 order = db.query(models.Order).filter_by(
#                     id=data['order_id'],
#                     store_id=session.store_id
#                 ).first()
#
#                 if not order:
#                     return {'error': 'Pedido não encontrado nesta loja'}
#
#                 # 4. Valida o novo status (exemplo com enum)
#                 valid_statuses = ['pending', 'preparing', 'ready', 'delivered']
#                 if data['new_status'] not in valid_statuses:
#                     return {'error': 'Status inválido'}
#
#                 # 5. Atualização segura
#                 order.order_status = data['new_status']
#                 db.commit()
#                 db.refresh(order)
#
#                 # 6. Notificação
#                 await admin_emit_order_updated_from_obj(order)
#                 print(f"✅ [Session {sid}] Pedido {order.id} atualizado para: {data['new_status']}")
#
#                 return {'success': True, 'order_id': order.id, 'new_status': order.order_status}
#
#             except Exception as e:
#                 db.rollback()
#                 print(f"❌ Erro ao atualizar pedido: {str(e)}")
#                 return {'error': 'Falha interna'}
#
#     async def on_update_store_settings(self, sid, data):
#         with get_db_manager() as db:
#             # Agora verificamos a sessão em vez do totem diretamente
#             session = db.query(models.StoreSession).filter_by(sid=sid, client_type='admin').first()
#             if not session:
#                 return {'error': 'Sessão não encontrada ou não autorizada'}
#
#             store = db.query(models.Store).filter_by(id=session.store_id).first()
#             if not store:
#                 return {"error": "Loja associada não encontrada"}
#
#             settings = db.query(models.StoreSettings).filter_by(store_id=store.id).first()
#             if not settings:
#                 return {"error": "Configurações não encontradas"}
#
#             try:
#                 for field in [
#                     "is_delivery_active", "is_takeout_active", "is_table_service_active",
#                     "is_store_open", "auto_accept_orders", "auto_print_orders"
#                 ]:
#                     if field in data:
#                         setattr(settings, field, data[field])
#
#                 db.commit()
#                 db.refresh(settings)
#                 db.refresh(store)
#
#                 await admin_emit_store_updated(store)
#                 await admin_emit_store_full_updated(db, store.id)
#
#                 return StoreSettingsBase.model_validate(settings).model_dump(mode='json')
#
#             except Exception as e:
#                 db.rollback()
#                 print(f"❌ Erro ao atualizar configurações da loja: {str(e)}")
#                 return {"error": str(e)}
#
#
#     async def on_join_store_room(self, sid, data):
#         try:
#             store_id = data.get("store_id")
#             if not store_id:
#                 print("❌ store_id ausente em join_store_room")
#                 return
#
#             room = f"admin_store_{store_id}"
#             await self.enter_room(sid, room)
#             print(f"✅ Admin entrou na sala dinâmica: {room}")
#         except Exception as e:
#             print(f"❌ Erro ao entrar na sala da loja {store_id}: {e}")
#
#     async def on_leave_store_room(self, sid, data):
#         try:
#             store_id = data.get("store_id")
#             if not store_id:
#                 print("❌ store_id ausente em leave_store_room")
#                 return
#
#             room = f"admin_store_{store_id}"
#             await self.leave_room(sid, room)
#             print(f"🚪 Admin saiu da sala: {room}")
#         except Exception as e:
#             print(f"❌ Erro ao sair da sala da loja {store_id}: {e}")
