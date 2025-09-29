from sqlalchemy import select
from datetime import datetime, timedelta
from urllib.parse import parse_qs

from src.api.admin.services.store_access_service import StoreAccessService
from src.api.admin.services.store_session_service import SessionService
from src.core import models

from src.core.database import get_db_manager
from src.socketio_instance import sio

# ✅ Importa a NOVA função de autorização correta
from src.api.admin.utils.authorize_admin import authorize_admin_by_jwt

async def handle_admin_connect(self, sid, environ):
    print(f"[ADMIN] Tentativa de conexão: {sid}")

    query = parse_qs(environ.get("QUERY_STRING", ""))
    token = query.get("admin_token", [None])[0]

    if not token:
        raise ConnectionRefusedError("Token obrigatório")

    self.environ[sid] = environ

    with get_db_manager() as db:
        try:
            # ✅ CORREÇÃO 1: A variável agora contém um objeto User.
            admin_user = await authorize_admin_by_jwt(db, token)

            if not admin_user or not admin_user.id:
                print(f"⚠️ Admin {sid} conectado, mas não autorizado pelo JWT.")
                raise ConnectionRefusedError("Acesso negado: Admin inválido.")

            admin_id = admin_user.id
            print(f"✅ Admin {admin_user.email} (ID: {admin_id}) autenticado com sucesso.")

            # Lógica de sessão única
            old_sessions = db.query(models.StoreSession).filter(
                models.StoreSession.user_id == admin_id,
                models.StoreSession.client_type == 'admin',
                models.StoreSession.sid != sid
            ).all()

            if old_sessions:
                print(f"🔌 Encontrada(s) {len(old_sessions)} sessão(ões) antiga(s) para o admin {admin_id}. Desconectando...")
                for old_session in old_sessions:
                    await sio.disconnect(old_session.sid, namespace='/admin')
                    db.delete(old_session)
                db.commit()

            # Entrar na sala de notificações
            notification_room = f"admin_notifications_{admin_id}"
            await self.enter_room(sid, notification_room)
            print(f"✅ Admin {sid} (ID: {admin_id}) entrou na sala de notificações: {notification_room}")

            # ✅ CORREÇÃO 2: Passa o objeto 'admin_user' correto para o serviço.
            all_accessible_store_ids = StoreAccessService.get_accessible_store_ids_with_fallback(
                db, admin_user
            )

            # ✅ CORREÇÃO 3: Garantir que all_accessible_store_ids seja uma lista
            if all_accessible_store_ids is None:
                all_accessible_store_ids = []
            elif not isinstance(all_accessible_store_ids, list):
                all_accessible_store_ids = list(all_accessible_store_ids)

            # Lógica de lojas consolidadas
            consolidated_store_ids = list(db.execute(
                select(models.AdminConsolidatedStoreSelection.store_id).where(
                    models.AdminConsolidatedStoreSelection.admin_id == admin_id
                )
            ).scalars())

            # ✅ CORREÇÃO 4: Só atribuir loja padrão se houver lojas acessíveis
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

            # Criar/atualizar sessão
            SessionService.create_or_update_session(
                db,
                sid=sid,
                user_id=admin_id,
                # ✅ CORREÇÃO 5: Só passar store_id se houver consolidated_store_ids
                store_id=consolidated_store_ids[0] if consolidated_store_ids else None,
                client_type="admin"
            )

            print(f"✅ Session criada/atualizada para sid {sid} com lojas consolidadas: {consolidated_store_ids}")

            # ✅ CORREÇÃO 6: Lógica otimizada para construção da lista de lojas
            stores_list_data = []
            if all_accessible_store_ids:  # Só faz query se houver IDs
                accessible_stores_objs = db.query(models.Store).filter(
                    models.Store.id.in_(all_accessible_store_ids)
                ).all()

                for store in accessible_stores_objs:
                    stores_list_data.append({
                        "id": store.id,
                        "name": store.name,
                        "is_consolidated": store.id in consolidated_store_ids,
                    })

            # ✅ CORREÇÃO 7: Log único e claro
            print(f"🔍 [DEBUG] Enviando admin_stores_list para SID {sid}: {len(stores_list_data)} lojas")

            # ✅ CORREÇÃO 8: Emissão organizada e consistente
            # SEMPRE emite admin_stores_list, mesmo com lista vazia
            await self.emit("admin_stores_list", {"stores": stores_list_data}, to=sid)

            # Emite evento específico se usuário não tem lojas
            if not stores_list_data:
                print(f"🔵 [Socket] Usuário {admin_id} não tem lojas - emitindo user_has_no_stores")
                await self.emit("user_has_no_stores", {
                    "user_id": admin_id,
                    "message": "Você não possui lojas. Crie uma nova loja para começar."
                }, to=sid)
            else:
                print(f"✅ [Socket] Usuário {admin_id} tem {len(stores_list_data)} lojas")

            # Emite consolidated_stores_updated (sempre, mesmo vazio)
            await self.emit("consolidated_stores_updated", {
                "store_ids": consolidated_store_ids
            }, to=sid)

            print(f"✅ Conexão do admin {admin_id} (SID: {sid}) finalizada com sucesso")

        except Exception as e:
            db.rollback()
            print(f"❌ Erro na conexão do admin (SID: {sid}): {str(e)}")
            # ✅ CORREÇÃO 9: Limpeza do environ em caso de erro
            self.environ.pop(sid, None)
            raise ConnectionRefusedError(f"Falha na autenticação: {str(e)}")

async def handle_admin_disconnect(self, sid):
    print(f"[ADMIN] Desconexão: {sid}")
    with get_db_manager() as db:
        try:
            session = db.query(models.StoreSession).filter_by(sid=sid).first()
            if session:
                db.delete(session)
                db.commit()
                print(f"✅ Session removida para sid {sid}")
            else:
                print(f"ℹ️  Nenhuma session encontrada para SID {sid}")

            # ✅ CORREÇÃO 10: Sempre limpar o environ, mesmo sem session
            self.environ.pop(sid, None)
            print(f"✅ Environ limpo para SID {sid}")

        except Exception as e:
            print(f"❌ Erro na desconexão do SID {sid}: {str(e)}")
            db.rollback()
            # Tentar limpar o environ mesmo em caso de erro
            try:
                self.environ.pop(sid, None)
            except:
                pass