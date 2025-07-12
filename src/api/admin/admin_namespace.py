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
                totem_auth = await authorize_admin(db, token)
                if not totem_auth or not totem_auth.id:  # Apenas admin_id é suficiente para auth agora
                    print(f"⚠️ Admin {sid} conectado, mas sem admin_id.")
                    raise ConnectionRefusedError("Acesso negado: Admin inválido.")

                admin_id = totem_auth.id

                # 1. Recupera as lojas que o admin selecionou para consolidação
                consolidated_store_ids = [
                    s.store_id
                    for s in db.execute(
                        select(models.AdminConsolidatedStoreSelection.store_id).where(
                            models.AdminConsolidatedStoreSelection.admin_id == admin_id
                        )
                    ).scalars()
                ]

                # Se não houver lojas selecionadas para consolidação, por padrão,
                # selecione APENAS a loja principal do admin, se existir.
                if not consolidated_store_ids and totem_auth.store_id:  # Verifica se totem_auth.store_id existe
                    consolidated_store_ids.append(totem_auth.store_id)

                # 2. Criar/atualizar sessão na tabela store_sessions
                session = db.query(models.StoreSession).filter_by(sid=sid).first()
                if not session:
                    session = models.StoreSession(
                        sid=sid,
                        store_id=consolidated_store_ids[0] if consolidated_store_ids else None,
                        # A 'store_id' aqui é a loja ATIVA padrão, não a consolidada
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

                # 3. Fazer o SID entrar nas rooms de TODAS as lojas consolidadas
                for store_id_to_join in consolidated_store_ids:
                    room = f"admin_store_{store_id_to_join}"
                    await self.enter_room(sid, room)
                    print(f"✅ Admin {sid} entrou na room para consolidação: {room}")
                    # Emitir dados iniciais para CADA UMA das lojas consolidadas para este SID
                    await self._emit_initial_data(db, store_id_to_join, sid)

                # 4. Enviar a lista COMPLETA de lojas que o admin tem acesso (para o seletor)
                # e quais estão ativas para consolidação
                # ASSUMIMOS QUE authorize_admin RETORNA UM OBJETO 'totem_auth'
                # QUE TEM UMA RELAÇÃO OU LISTA DE TODAS AS LOJAS QUE ESTE ADMIN PODE GERENCIAR.
                # Se não, você precisará buscar essas lojas aqui.
                # Exemplo: totem_auth.admin.stores, ou buscar por models.AdminStoreAccess

                # Exemplo de como buscar TODAS as lojas acessíveis pelo admin (se totem_auth não as trouxer)
                # Você pode precisar de um modelo AdminStoreAccess ou similar
                all_accessible_store_ids = [s.store_id for s in
                                            db.query(models.AdminStoreAccess).filter_by(admin_id=admin_id).all()]
                all_accessible_stores = db.query(models.Store).filter(
                    models.Store.id.in_(all_accessible_store_ids)).all()

                stores_list_data = []
                for store in all_accessible_stores:
                    stores_list_data.append({
                        "id": store.id,
                        "name": store.name,  # Assumindo que models.Store tem 'name'
                        "is_consolidated": store.id in consolidated_store_ids,
                    })

                # Se all_accessible_stores estiver vazia e totem_auth.store_id existir, adicione a principal
                if not stores_list_data and totem_auth.store_id:
                    stores_list_data.append({
                        "id": totem_auth.store_id,
                        "name": totem_auth.store.name,
                        "is_consolidated": totem_auth.store_id in consolidated_store_ids,
                    })

                await self.emit("admin_stores_list", {"stores": stores_list_data}, to=sid)
                await self.emit("consolidated_stores_updated", {"store_ids": consolidated_store_ids},
                                to=sid)  # Garante que o frontend saiba quais estão consolidadas
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
                    # Não é necessário fazer o leave_room explícito aqui, o socketio já faz na desconexão.
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

                query = parse_qs(self.environ[sid].get("QUERY_STRING", ""))
                token = query.get("admin_token", [None])[0]
                if not token:
                    return {"error": "Token obrigatório para esta operação"}
                totem_auth = await authorize_admin(db, token)
                if not totem_auth or not totem_auth.id:
                    return {"error": "Admin não autorizado"}

                admin_id = totem_auth.id

                # Buscar TODAS as lojas que este admin TEM PERMISSÃO para gerenciar
                # Esta lógica deve espelhar a do on_connect para consistência
                all_accessible_store_ids_for_admin = [s.store_id for s in db.query(models.AdminStoreAccess).filter_by(
                    admin_id=admin_id).all()]

                # Se admin não tem nenhuma loja acessível definida explicitamente, mas tem uma 'principal'
                if not all_accessible_store_ids_for_admin and totem_auth.store_id:
                    all_accessible_store_ids_for_admin.append(totem_auth.store_id)

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
                    await self.leave_room(sid, room)  # O SID sai da room
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
                    # **NOVA VALIDAÇÃO**: Valide se o admin realmente tem acesso a esta loja
                    if store_id_to_add not in all_accessible_store_ids_for_admin:
                        print(
                            f"⚠️ Admin {sid} tentou adicionar loja {store_id_to_add}"
                            f" sem permissão."
                        )
                        continue  # Pula esta loja

                    room = f"admin_store_{store_id_to_add}"
                    await self.enter_room(sid, room)  # O SID entra na room
                    try:
                        new_selection = models.AdminConsolidatedStoreSelection(
                            admin_id=admin_id, store_id=store_id_to_add
                        )
                        db.add(new_selection)
                        db.commit()
                        print(
                            f"✅ Admin {sid} entrou na sala e adicionou seleção da loja:"
                            f" {store_id_to_add}"
                        )
                        # Opcional: Emitir dados iniciais para a loja recém-adicionada
                        await self._emit_initial_data(db, store_id_to_add, sid)
                    except IntegrityError:
                        db.rollback()
                        print(
                            f"⚠️ Seleção de loja {store_id_to_add} já existia para admin"
                            f" {admin_id}."
                        )
                        await self.enter_room(sid, room)  # Garante que ele esteja na room
                    except Exception as add_e:
                        db.rollback()
                        print(
                            f"❌ Erro ao adicionar seleção da loja {store_id_to_add}:"
                            f" {str(add_e)}"
                        )

                # Emitir a nova lista de lojas consolidadas para o frontend (globalmente, para esta sessão)
                # Isso garante que o StoresManagerCubit no Flutter atualize sua lista de lojas consolidadas
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
                    to=sid,  # Emitir apenas para o SID que fez a requisição
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
        # Emite dados para um SID específico, se fornecido, ou para a room da loja
        # O SID é usado em on_connect e on_set_consolidated_stores para emitir dados iniciais
        # para o cliente que se conectou/alterou a seleção.
        await admin_emit_store_full_updated(db, store_id, sid=sid)
        await admin_product_list_all(db, store_id, sid=sid)
        await admin_emit_orders_initial(db, store_id, sid=sid)

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

                # ** SAÍDA DA SALA ANTIGA: Importante para gerenciar a "loja ativa" no frontend **
                # Isso permite que o frontend mostre detalhes de APENAS UMA loja por vez.
                if session.store_id and session.store_id != store_id:
                    old_room = f"admin_store_{session.store_id}"
                    await self.leave_room(sid, old_room)
                    print(f"🚪 Admin {sid} saiu da sala antiga: {old_room}")

                # Entrar na nova sala
                new_room = f"admin_store_{store_id}"
                await self.enter_room(sid, new_room)
                print(f"✅ Admin {sid} entrou na sala dinâmica: {new_room}")

                # Atualizar a loja ativa na sessão (representa a loja que o admin está visualizando no momento)
                session.store_id = store_id
                db.commit()

                # Emitir dados iniciais para o SID para a NOVA loja (detalhes específicos)
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
                if session.store_id == store_id:  # Verifica se é a loja ativa antes de sair da room dela
                    room = f"admin_store_{store_id}"
                    await self.leave_room(sid, room)
                    print(f"🚪 Admin {sid} saiu da sala: {room}")
                    # Opcional: Limpar session.store_id ou definir como uma loja padrão após sair.
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

                # 2. Verifica a sessão para obter o admin_id
                session = db.query(models.StoreSession).filter_by(sid=sid, client_type='admin').first()
                if not session:
                    return {'error': 'Sessão não autorizada'}

                query_params = parse_qs(self.environ[sid].get("QUERY_STRING", ""))
                admin_token = query_params.get("admin_token", [None])[0]
                if not admin_token:
                    return {"error": "Token de admin não encontrado na sessão."}

                totem_auth = await authorize_admin(db, admin_token)
                if not totem_auth or not totem_auth.id:
                    return {"error": "Admin não autorizado."}

                admin_id = totem_auth.id

                # 3. Busca TODAS as lojas que este admin TEM PERMISSÃO para gerenciar
                # Esta lógica deve espelhar a do on_connect para consistência
                all_accessible_store_ids_for_admin = [s.store_id for s in db.query(models.AdminStoreAccess).filter_by(
                    admin_id=admin_id).all()]
                if not all_accessible_store_ids_for_admin and totem_auth.store_id:
                    all_accessible_store_ids_for_admin.append(totem_auth.store_id)

                if not all_accessible_store_ids_for_admin:
                    return {'error': 'Admin não possui lojas acessíveis para gerenciar pedidos.'}

                # 4. Busca o pedido APENAS pelo ID, e então verifica se ele pertence a uma das lojas acessíveis
                order = db.query(models.Order).filter_by(id=data['order_id']).first()

                if not order:
                    return {'error': 'Pedido não encontrado.'}

                # 5. Valida se o pedido pertence a uma das lojas que o admin tem acesso
                if order.store_id not in all_accessible_store_ids_for_admin:
                    return {'error': 'Acesso negado: Pedido não pertence a uma das suas lojas.'}

                # 6. Valida o novo status
                valid_statuses = ['pending', 'preparing', 'ready', 'delivered']  # Adapte se houver mais statuses
                if data['new_status'] not in valid_statuses:
                    return {'error': 'Status inválido'}

                # 7. Atualização segura
                order.order_status = data['new_status']
                db.commit()
                db.refresh(order)

                # 8. Notificação
                # Emite a atualização para a sala específica da loja do pedido
                # E também para o SID que fez a requisição, se necessário (admin_emit_order_updated_from_obj já faz isso)
                await admin_emit_order_updated_from_obj(order)
                print(
                    f"✅ [Session {sid}] Pedido {order.id} da loja {order.store_id} atualizado para: {data['new_status']}")

                return {'success': True, 'order_id': order.id, 'new_status': order.order_status}

            except Exception as e:
                db.rollback()
                print(f"❌ Erro ao atualizar pedido: {str(e)}")
                return {'error': 'Falha interna'}

    async def on_update_store_settings(self, sid, data):
        with get_db_manager() as db:
            session = db.query(models.StoreSession).filter_by(sid=sid, client_type='admin').first()
            if not session:
                return {'error': 'Sessão não encontrada ou não autorizada'}

            # ** AQUI: Verifique se o store_id da requisição é permitido para este admin **
            # O frontend deve enviar qual store_id ele quer atualizar as settings
            requested_store_id = data.get("store_id")
            if not requested_store_id:
                return {'error': 'ID da loja é obrigatório para atualizar configurações.'}

            query_params = parse_qs(self.environ[sid].get("QUERY_STRING", ""))
            admin_token = query_params.get("admin_token", [None])[0]
            if not admin_token:
                return {"error": "Token de admin não encontrado na sessão."}

            totem_auth = await authorize_admin(db, admin_token)
            if not totem_auth or not totem_auth.id:
                return {"error": "Admin não autorizado."}

            admin_id = totem_auth.id

            all_accessible_store_ids_for_admin = [s.store_id for s in
                                                  db.query(models.AdminStoreAccess).filter_by(admin_id=admin_id).all()]
            if not all_accessible_store_ids_for_admin and totem_auth.store_id:
                all_accessible_store_ids_for_admin.append(totem_auth.store_id)

            if requested_store_id not in all_accessible_store_ids_for_admin:
                return {'error': 'Acesso negado: Você não tem permissão para gerenciar esta loja.'}

            store = db.query(models.Store).filter_by(id=requested_store_id).first()  # Usa o requested_store_id
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
                db.refresh(store)

                # Emite atualização para a sala da loja (todos os admins e totens nela)
                await admin_emit_store_updated(store)
                await admin_emit_store_full_updated(db, store.id)  # Emite para a sala da loja e o SID que solicitou

                return StoreSettingsBase.model_validate(settings).model_dump(mode='json')

            except Exception as e:
                db.rollback()
                print(f"❌ Erro ao atualizar configurações da loja: {str(e)}")
                return {"error": str(e)}