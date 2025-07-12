from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import joinedload  # Já importado, bom para joins complexos
from sqlalchemy import select, delete
from datetime import datetime
from urllib.parse import parse_qs
from socketio import AsyncNamespace
from src.api.admin.schemas.store_settings import StoreSettingsBase
from src.api.app.events.socketio_emitters import emit_store_updated
from src.core import models  # Importa seus modelos (User, Role, StoreAccess, etc.)
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
                # authorize_admin agora precisa retornar o objeto AdminUser (ou User) com seu ID e papel
                # Supondo que authorize_admin já valida se é um admin e retorna o objeto User autenticado
                totem_auth_user = await authorize_admin(db, token)  # Renomeado para evitar confusão com 'totem'
                if not totem_auth_user or not totem_auth_user.id:
                    print(f"⚠️ Admin {sid} conectado, mas sem admin_id.")
                    raise ConnectionRefusedError("Acesso negado: Admin inválido.")

                admin_id = totem_auth_user.id

                # 1. Obter os roles do usuário para saber se ele é um admin
                # Você precisaria de uma query para verificar se o usuário tem a role 'admin'
                # ou se authorize_admin já garante isso. Para esta lógica, assumiremos que totem_auth_user.id é um admin_id válido.

                # 2. Recuperar TODAS as lojas às quais este admin tem acesso através da tabela StoreAccess
                # Assumimos que 'admin' role_id é necessário para gerenciar
                # OU que StoreAccess já implica acesso administrativo
                admin_role = db.query(models.Role).filter_by(machine_name='admin').first()
                if not admin_role:
                    print("❌ Role 'admin' não encontrada no banco de dados.")
                    raise ConnectionRefusedError("Configuração de roles inválida.")

                all_accessible_store_ids = [
                    sa.store_id
                    for sa in db.query(models.StoreAccess).filter_by(
                        user_id=admin_id, role_id=admin_role.id  # Garante que só pega lojas que o user é 'admin'
                    ).all()
                ]

                # Se o admin não tiver StoreAccess específico como 'admin', mas authorize_admin já o validou
                # como admin principal de UMA loja (totem_auth_user.store_id), podemos adicioná-la.
                # Isso depende do seu fluxo de authorize_admin e como o admin principal de uma loja é definido.
                # Se StoreAccess for a única fonte de verdade para acesso a lojas, remova essa parte.
                if not all_accessible_store_ids and totem_auth_user.store_id:
                    all_accessible_store_ids.append(totem_auth_user.store_id)

                # 3. Recupera as lojas que o admin selecionou para consolidação (persistido no DB)
                consolidated_store_ids = [
                    s.store_id
                    for s in db.execute(
                        select(models.AdminConsolidatedStoreSelection.store_id).where(
                            models.AdminConsolidatedStoreSelection.admin_id == admin_id
                        )
                    ).scalars()
                ]

                # Se não houver lojas selecionadas para consolidação, por padrão,
                # selecione todas as lojas às quais ele tem acesso se forem poucas, ou a principal.
                # Vamos usar a lógica de se não houver seleção consolidada, use todas as acessíveis.
                if not consolidated_store_ids and all_accessible_store_ids:
                    consolidated_store_ids = list(all_accessible_store_ids)
                elif not consolidated_store_ids and totem_auth_user.store_id:  # Fallback para a principal se nada mais
                    consolidated_store_ids.append(totem_auth_user.store_id)

                # 4. Criar/atualizar sessão na tabela store_sessions
                session = db.query(models.StoreSession).filter_by(sid=sid).first()
                if not session:
                    session = models.StoreSession(
                        sid=sid,
                        store_id=consolidated_store_ids[0] if consolidated_store_ids else None,  # Loja ATIVA padrão
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

                # 5. Fazer o SID entrar nas rooms de TODAS as lojas consolidadas
                for store_id_to_join in consolidated_store_ids:
                    room = f"admin_store_{store_id_to_join}"
                    await self.enter_room(sid, room)
                    print(f"✅ Admin {sid} entrou na room para consolidação: {room}")
                    await self._emit_initial_data(db, store_id_to_join, sid)

                # 6. Enviar a lista COMPLETA de lojas que o admin tem acesso (para o seletor)
                stores_list_data = []
                # Precisamos carregar os nomes das lojas a partir dos IDs
                accessible_stores_objs = db.query(models.Store).filter(
                    models.Store.id.in_(all_accessible_store_ids)).all()

                for store in accessible_stores_objs:
                    stores_list_data.append({
                        "id": store.id,
                        "name": store.name,
                        "is_consolidated": store.id in consolidated_store_ids,
                    })

                # Se ainda não houver lojas (muito improvável aqui), e totem_auth_user.store_id existir, adicione a principal
                if not stores_list_data and totem_auth_user.store_id:
                    stores_list_data.append({
                        "id": totem_auth_user.store_id,
                        "name": totem_auth_user.store.name,  # Assumindo que totem_auth_user.store tem um nome
                        "is_consolidated": totem_auth_user.store_id in consolidated_store_ids,
                    })

                await self.emit("admin_stores_list", {"stores": stores_list_data}, to=sid)
                await self.emit("consolidated_stores_updated", {"store_ids": consolidated_store_ids}, to=sid)
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
                totem_auth_user = await authorize_admin(db, token)
                if not totem_auth_user or not totem_auth_user.id:
                    return {"error": "Admin não autorizado"}

                admin_id = totem_auth_user.id

                # Obter a role 'admin'
                admin_role = db.query(models.Role).filter_by(machine_name='admin').first()
                if not admin_role:
                    return {"error": "Configuração de roles inválida: 'admin' role não encontrada."}

                # Buscar TODAS as lojas que este admin TEM PERMISSÃO para gerenciar
                all_accessible_store_ids_for_admin = [
                    sa.store_id
                    for sa in db.query(models.StoreAccess).filter_by(
                        user_id=admin_id, role_id=admin_role.id
                    ).all()
                ]
                # Fallback para a loja principal se não houver StoreAccess explícito
                if not all_accessible_store_ids_for_admin and totem_auth_user.store_id:
                    all_accessible_store_ids_for_admin.append(totem_auth_user.store_id)

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
                    # **NOVA VALIDAÇÃO**: Valide se o admin realmente tem acesso a esta loja
                    if store_id_to_add not in all_accessible_store_ids_for_admin:
                        print(
                            f"⚠️ Admin {sid} tentou adicionar loja {store_id_to_add}"
                            f" sem permissão."
                        )
                        continue

                    room = f"admin_store_{store_id_to_add}"
                    await self.enter_room(sid, room)
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
                        await self._emit_initial_data(db, store_id_to_add, sid)
                    except IntegrityError:
                        db.rollback()
                        print(
                            f"⚠️ Seleção de loja {store_id_to_add} já existia para admin"
                            f" {admin_id}."
                        )
                        await self.enter_room(sid, room)
                    except Exception as add_e:
                        db.rollback()
                        print(
                            f"❌ Erro ao adicionar seleção da loja {store_id_to_add}:"
                            f" {str(add_e)}"
                        )

                # Emitir a nova lista de lojas consolidadas para o frontend
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

                if session.store_id and session.store_id != store_id:
                    old_room = f"admin_store_{session.store_id}"
                    await self.leave_room(sid, old_room)
                    print(f"🚪 Admin {sid} saiu da sala antiga: {old_room}")

                new_room = f"admin_store_{store_id}"
                await self.enter_room(sid, new_room)
                print(f"✅ Admin {sid} entrou na sala dinâmica: {new_room}")

                session.store_id = store_id
                db.commit()

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

                if session.store_id == store_id:
                    room = f"admin_store_{store_id}"
                    await self.leave_room(sid, room)
                    print(f"🚪 Admin {sid} saiu da sala: {room}")
                else:
                    print(f"⚠️ Admin {sid} tentou sair da loja {store_id}, mas a loja ativa era {session.store_id}.")
        except Exception as e:
            print(f"❌ Erro ao sair da sala da loja {store_id}: {e}")

    async def on_update_order_status(self, sid, data):
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

                totem_auth_user = await authorize_admin(db, admin_token)
                if not totem_auth_user or not totem_auth_user.id:
                    return {"error": "Admin não autorizado."}

                admin_id = totem_auth_user.id

                # Obter a role 'admin'
                admin_role = db.query(models.Role).filter_by(machine_name='admin').first()
                if not admin_role:
                    return {"error": "Configuração de roles inválida: 'admin' role não encontrada."}

                # Buscar TODAS as lojas que este admin TEM PERMISSÃO para gerenciar
                all_accessible_store_ids_for_admin = [
                    sa.store_id
                    for sa in db.query(models.StoreAccess).filter_by(
                        user_id=admin_id, role_id=admin_role.id
                    ).all()
                ]
                # Fallback para a loja principal se não houver StoreAccess explícito
                if not all_accessible_store_ids_for_admin and totem_auth_user.store_id:
                    all_accessible_store_ids_for_admin.append(totem_auth_user.store_id)

                if not all_accessible_store_ids_for_admin:
                    return {'error': 'Admin não possui lojas acessíveis para gerenciar pedidos.'}

                order = db.query(models.Order).filter_by(id=data['order_id']).first()

                if not order:
                    return {'error': 'Pedido não encontrado.'}

                if order.store_id not in all_accessible_store_ids_for_admin:
                    return {'error': 'Acesso negado: Pedido não pertence a uma das suas lojas.'}

                valid_statuses = ['pending', 'preparing', 'ready', 'delivered']
                if data['new_status'] not in valid_statuses:
                    return {'error': 'Status inválido'}

                order.order_status = data['new_status']
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

    async def on_update_store_settings(self, sid, data):
        with get_db_manager() as db:
            session = db.query(models.StoreSession).filter_by(sid=sid, client_type='admin').first()
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

            # Obter a role 'admin'
            admin_role = db.query(models.Role).filter_by(machine_name='admin').first()
            if not admin_role:
                return {"error": "Configuração de roles inválida: 'admin' role não encontrada."}

            all_accessible_store_ids_for_admin = [
                sa.store_id
                for sa in db.query(models.StoreAccess).filter_by(
                    user_id=admin_id, role_id=admin_role.id
                ).all()
            ]
            # Fallback para a loja principal se não houver StoreAccess explícito
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
                db.refresh(store)

                await admin_emit_store_updated(store)
                await admin_emit_store_full_updated(db, store.id)

                return StoreSettingsBase.model_validate(settings).model_dump(mode='json')

            except Exception as e:
                db.rollback()
                print(f"❌ Erro ao atualizar configurações da loja: {str(e)}")
                return {"error": str(e)}