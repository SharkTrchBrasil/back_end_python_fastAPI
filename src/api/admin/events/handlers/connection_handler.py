import asyncio
from sqlalchemy import select
from datetime import datetime, timedelta
from urllib.parse import parse_qs

from src.api.admin.services.store_access_service import StoreAccessService
from src.api.admin.services.store_session_service import SessionService
from src.api.schemas.store.store import StoreWithRole
from src.core import models
from src.core.database import get_db_manager
from src.socketio_instance import sio
from src.api.admin.utils.authorize_admin import authorize_admin_by_jwt


async def handle_admin_connect(self, sid, environ):
    """
    Manipulador de conexão do admin.
    - Autentica o usuário via JWT.
    - Gerencia sessões únicas.
    - Envia a lista COMPLETA de lojas acessíveis, incluindo detalhes da assinatura.
    - Configura a sessão e as salas de notificação.
    """
    print(f"[ADMIN] Tentativa de conexão: {sid}")

    query = parse_qs(environ.get("QUERY_STRING", ""))
    token = query.get("admin_token", [None])[0]

    if not token:
        raise ConnectionRefusedError("Token obrigatório")

    self.environ[sid] = environ

    with get_db_manager() as db:
        try:
            admin_user = await authorize_admin_by_jwt(db, token)

            if not admin_user or not admin_user.id:
                raise ConnectionRefusedError("Acesso negado: Admin inválido.")

            admin_id = admin_user.id
            print(f"✅ Admin {admin_user.email} (ID: {admin_id}) autenticado com sucesso.")

            # Lógica de sessão única (inalterada)
            old_sessions = db.query(models.StoreSession).filter(
                models.StoreSession.user_id == admin_id,
                models.StoreSession.client_type == 'admin',
                models.StoreSession.sid != sid
            ).all()
            if old_sessions:
                print(
                    f"🔌 Encontrada(s) {len(old_sessions)} sessão(ões) antiga(s) para o admin {admin_id}. Desconectando...")
                for old_session in old_sessions:
                    await sio.disconnect(old_session.sid, namespace='/admin')
                    db.delete(old_session)
                db.commit()

            # Entrar na sala de notificações (inalterado)
            notification_room = f"admin_notifications_{admin_id}"
            await self.enter_room(sid, notification_room)
            print(f"✅ Admin {sid} (ID: {admin_id}) entrou na sala de notificações: {notification_room}")

            # ✅ PASSO 2: A LÓGICA DE CONSTRUÇÃO DA LISTA DE LOJAS FOI TOTALMENTE CORRIGIDA

            # Busca os objetos de acesso, que contêm a loja e a role.
            accessible_store_accesses = StoreAccessService.get_accessible_stores_with_roles(db, admin_user)

            stores_list_payload = []
            if accessible_store_accesses:
                # Itera sobre os objetos de acesso e usa o Pydantic para validar e serializar.
                # Isso aciona o @model_validator em StoreDetails para cada loja!
                print(f"🔧 Serializando {len(accessible_store_accesses)} loja(s) com o schema StoreWithRole...")
                for access in accessible_store_accesses:
                    store_with_role_schema = StoreWithRole.model_validate(access)
                    stores_list_payload.append(store_with_role_schema.model_dump(mode='json'))

            print(f"🔍 [DEBUG] Enviando admin_stores_list para SID {sid} com {len(stores_list_payload)} loja(s)")

            # Emite a lista de lojas, agora com a estrutura completa e correta.
            await self.emit("admin_stores_list", {"stores": stores_list_payload}, to=sid)

            # Lógica restante continua, mas agora usa os dados já buscados.
            if not stores_list_payload:
                print(f"🔵 [Socket] Usuário {admin_id} não tem lojas - emitindo user_has_no_stores")
                await self.emit("user_has_no_stores", {
                    "user_id": admin_id,
                    "message": "Você não possui lojas. Crie uma nova loja para começar."
                }, to=sid)
            else:
                print(f"✅ [Socket] Usuário {admin_id} tem {len(stores_list_payload)} lojas")

            # Lógica de lojas consolidadas (inalterada)
            consolidated_store_ids = list(db.execute(
                select(models.AdminConsolidatedStoreSelection.store_id).where(
                    models.AdminConsolidatedStoreSelection.admin_id == admin_id
                )
            ).scalars())

            all_accessible_store_ids = [access.store_id for access in accessible_store_accesses]
            if not consolidated_store_ids and all_accessible_store_ids:
                # Atribui a primeira loja da lista como padrão
                loja_padrao = all_accessible_store_ids[0]
                try:
                    nova_selecao = models.AdminConsolidatedStoreSelection(admin_id=admin_id, store_id=loja_padrao)
                    db.add(nova_selecao)
                    db.commit()
                    consolidated_store_ids = [loja_padrao]
                    print(f"✅ Loja padrão {loja_padrao} atribuída ao admin {admin_id}")
                except Exception as e:
                    db.rollback()
                    print(f"❌ Erro ao definir loja padrão: {e}")

            # Criar/atualizar sessão (inalterado)
            SessionService.create_or_update_session(
                db,
                sid=sid,
                user_id=admin_id,
                store_id=consolidated_store_ids[0] if consolidated_store_ids else None,
                client_type="admin"
            )

            # Emite o evento de lojas consolidadas (inalterado)
            await self.emit("consolidated_stores_updated", {"store_ids": consolidated_store_ids}, to=sid)

            print(f"🏁 Conexão do admin {admin_id} (SID: {sid}) finalizada com sucesso")

        except Exception as e:
            db.rollback()
            print(f"❌ Erro na conexão do admin (SID: {sid}): {str(e)}")
            self.environ.pop(sid, None)
            raise ConnectionRefusedError(f"Falha na autenticação: {str(e)}")


async def handle_admin_disconnect(self, sid):
    # Esta função não precisa de alterações.
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

            self.environ.pop(sid, None)
            print(f"✅ Environ limpo para SID {sid}")

        except Exception as e:
            print(f"❌ Erro na desconexão do SID {sid}: {str(e)}")
            db.rollback()
            try:
                self.environ.pop(sid, None)
            except:
                pass