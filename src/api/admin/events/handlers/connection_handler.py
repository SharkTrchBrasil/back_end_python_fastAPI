
from sqlalchemy import select
from datetime import datetime, timedelta
from urllib.parse import parse_qs

from src.api.admin.services.store_access_service import StoreAccessService
from src.api.admin.services.store_session_service import SessionService
from src.core import models

from src.api.admin.utils.authorize_admin import authorize_admin
from src.core.database import get_db_manager
from src.socketio_instance import sio


async def handle_admin_connect(self, sid, environ):
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

            # ✨ LÓGICA DE SESSÃO ÚNICA ✨
            # 1. Procura por sessões ANTIGAS do mesmo usuário
            old_sessions = db.query(models.StoreSession).filter(
                models.StoreSession.user_id == admin_id,
                models.StoreSession.client_type == 'admin',
                models.StoreSession.sid != sid  # Exclui a sessão atual que estamos criando
            ).all()

            if old_sessions:
                print(
                    f"🔌 Encontrada(s) {len(old_sessions)} sessão(ões) antiga(s) para o admin {admin_id}. Desconectando...")
                for old_session in old_sessions:
                    # 2. Manda um comando para o cliente antigo se desconectar
                    await sio.disconnect(old_session.sid, namespace='/admin')
                    # 3. Remove a sessão antiga do banco de dados
                    db.delete(old_session)
                db.commit()



            # --- NOVO: Entrar na sala de notificações pessoal e global ---
            # Este é o canal para notificações leves de TODAS as lojas do admin.
            notification_room = f"admin_notifications_{admin_id}"
            await self.enter_room(sid, notification_room)
            print(f"✅ Admin {sid} (ID: {admin_id}) entrou na sala de notificações: {notification_room}")
            # --- FIM DA MUDANÇA ---


            # Busca todas as lojas às quais o admin tem acesso com a role 'admin'
            all_accessible_store_ids = StoreAccessService.get_accessible_store_ids_with_fallback(
                db, totem_auth_user
            )

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

            SessionService.create_or_update_session(
                db,
                sid=sid,
                user_id=admin_id,  # Adicione este parâmetro
                store_id=consolidated_store_ids[0] if consolidated_store_ids else None,
                client_type="admin"
            )



            print(
                f"✅ Session criada/atualizada para sid {sid} com lojas consolidadas:"
                f" {consolidated_store_ids}"
            )


            # # 5. Fazer o SID entrar nas rooms de TODAS as lojas consolidadas
            # for store_id_to_join in consolidated_store_ids:
            #     room = f"admin_store_{store_id_to_join}"
            #     await self.enter_room(sid, room)
            #     print(f"✅ Admin {sid} entrou na room para consolidação: {room}")
            #     await self._emit_initial_data(db, store_id_to_join, sid)

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

            print(f"DEBUG BACKEND: [3] stores_list_data ANTES do fallback user_main_store: {stores_list_data}")
            if totem_auth_user.store_id and totem_auth_user.store_id not in [s['id'] for s in stores_list_data]:
                # Garante que 'store' está carregado no totem_auth_user
                user_main_store = db.query(models.Store).filter_by(id=totem_auth_user.store_id).first()
                if user_main_store:
                    stores_list_data.append({
                        "id": user_main_store.id,
                        "name": user_main_store.name,
                        "is_consolidated": user_main_store.id in consolidated_store_ids,
                    })
            print(f"DEBUG BACKEND: [4] stores_list_data FINAL enviado via 'admin_stores_list': {stores_list_data}")
            await self.emit("admin_stores_list", {"stores": stores_list_data}, to=sid)
            await self.emit("consolidated_stores_updated", {"store_ids": consolidated_store_ids}, to=sid)
            print(f"✅ Lista de lojas e seleção consolidada enviada para {sid}")

        except Exception as e:
            db.rollback()
            print(f"❌ Erro na conexão: {str(e)}")
            raise


async def handle_admin_disconnect(self, sid):
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