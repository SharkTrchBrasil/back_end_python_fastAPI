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

    def __init__(self, namespace=None):
        super().__init__(namespace)
        self.environ = {}  # Armazena o environ de cada conexão pelo sid

    async def on_connect(self, sid, environ):
        print(f"[ADMIN] Conexão estabelecida: {sid}")
        query = parse_qs(environ.get("QUERY_STRING", ""))
        token = query.get("admin_token", [None])[0]

        if not token:
            raise ConnectionRefusedError("Token obrigatório")

        self.environ[sid] = environ  # GUARDA O ENVIRON PARA EVENTOS FUTUROS

        with get_db_manager() as db:
            try:
                totem_auth_user = await authorize_admin(db, token)
                if not totem_auth_user or not totem_auth_user.id:
                    print(f"⚠️ Admin {sid} conectado, mas sem admin_id.")
                    raise ConnectionRefusedError("Acesso negado: Admin inválido.")

                admin_id = totem_auth_user.id

                # Busca todas as lojas às quais o admin tem acesso com a role 'admin'
                all_accessible_store_ids = [
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
                    f"DEBUG: all_accessible_store_ids para admin {admin_id} (por machine_name): {all_accessible_store_ids}")

                # Fallback: Se não houver StoreAccess explícito para role 'admin',
                # adiciona a loja principal associada diretamente ao usuário autenticado (se houver).
                if not all_accessible_store_ids and totem_auth_user.store_id:
                    all_accessible_store_ids.append(totem_auth_user.store_id)
                    print(
                        f"DEBUG: Adicionada store_id do usuário autenticado como fallback: {totem_auth_user.store_id}")

                # 3. Recupera as lojas que o admin selecionou para consolidação (persistido no DB)
                consolidated_store_ids = list(db.execute(
                    select(models.AdminConsolidatedStoreSelection.store_id).where(
                        models.AdminConsolidatedStoreSelection.admin_id == admin_id
                    )
                ).scalars())

                # 4. Se vazio, seleciona a primeira loja da lista de acessíveis e salva no DB como padrão
                if not consolidated_store_ids and all_accessible_store_ids:
                    loja_padrao = all_accessible_store_ids[0]

                    try:
                        nova_selecao = models.AdminConsolidatedStoreSelection(
                            admin_id=admin_id,
                            store_id=loja_padrao
                        )
                        db.add(nova_selecao)
                        db.commit()
                        consolidated_store_ids = [loja_padrao]
                        print(f"✅ Loja padrão {loja_padrao} atribuída ao admin {admin_id}")
                    except Exception as e:
                        db.rollback()
                        print(f"❌ Erro ao definir loja padrão: {e}")

                # 4. Criar/atualizar sessão na tabela store_sessions
                session = db.query(models.StoreSession).filter_by(sid=sid).first()
                if not session:
                    session = models.StoreSession(
                        sid=sid,
                        store_id=consolidated_store_ids[0] if consolidated_store_ids else None,
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
                accessible_stores_objs = db.query(models.Store).filter(
                    models.Store.id.in_(all_accessible_store_ids)).all()

                for store in accessible_stores_objs:
                    stores_list_data.append({
                        "id": store.id,
                        "name": store.name,
                        "is_consolidated": store.id in consolidated_store_ids,
                    })

                # Se ainda não houver lojas na lista (muito improvável após os filtros),
                # e totem_auth_user.store_id existir e não estiver já na lista, adicione a principal.
                # Isso cobre casos onde all_accessible_store_ids foi populado apenas pelo fallback.
                if totem_auth_user.store_id and totem_auth_user.store_id not in [s['id'] for s in stores_list_data]:
                     # Garante que 'store' está carregado no totem_auth_user
                    user_main_store = db.query(models.Store).filter_by(id=totem_auth_user.store_id).first()
                    if user_main_store:
                        stores_list_data.append({
                            "id": user_main_store.id,
                            "name": user_main_store.name,
                            "is_consolidated": user_main_store.id in consolidated_store_ids,
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

                    self.environ.pop(sid, None)
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
                    # VALIDAÇÃO: Valide se o admin realmente tem acesso a esta loja
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
                updated_consolidated_ids = list(db.execute(
                    select(models.AdminConsolidatedStoreSelection.store_id).where(
                        models.AdminConsolidatedStoreSelection.admin_id == admin_id
                    )
                ).scalars())

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

                valid_statuses = [
                    'pending',  # Criado
                    'preparing',  # Sendo preparado
                    'ready',  # Pronto para entrega/retirada
                    'on_route',  # Está a caminho
                    'delivered',  # Entregue com sucesso
                    'canceled'  # Cancelado por qualquer motivo
                ]

                if data['new_status'] not in valid_statuses:
                    return {'error': 'Status inválido'}

                old_status = order.order_status  # Salva o status atual antes de mudar

                order.order_status = data['new_status']

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
                    if old_status in ['ready', 'on_route', 'delivered']: # Só reverte se já havia sido 'tirado' do estoque
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

            # *** CORREÇÃO APLICADA AQUI: Adicionar a lógica de busca de lojas acessíveis ***
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
                db.refresh(store) # Refresh na store para garantir que as configurações sejam atualizadas ao emitir

                await admin_emit_store_updated(store)
                await admin_emit_store_full_updated(db, store.id)

                return StoreSettingsBase.model_validate(settings).model_dump(mode='json')

            except Exception as e:
                db.rollback()
                print(f"❌ Erro ao atualizar configurações da loja: {str(e)}")
                return {"error": str(e)}