from urllib.parse import parse_qs

from src.api.admin.services.store_access_service import StoreAccessService
from src.api.admin.services.store_session_service import SessionService
from src.api.admin.services.store_transformer_service import StoreTransformerService
from src.api.admin.services.subscription_service import SubscriptionService  # ← NOVO

from src.api.schemas.store.store_with_role import StoreWithRole

from src.core import models
from src.core.database import get_db_manager
from src.socketio_instance import sio
from src.api.admin.utils.authorize_admin import authorize_admin_by_jwt


async def handle_admin_connect(self, sid, environ):
    """
    Manipulador de conexão do admin.
    Captura informações do dispositivo para gerenciamento de sessões.
    """
    print(f"[ADMIN] Tentativa de conexão: {sid}")

    query = parse_qs(environ.get("QUERY_STRING", ""))
    token = query.get("admin_token", [None])[0]

    # ✅ NOVO: Captura informações do dispositivo
    device_name = query.get("device_name", ["Unknown Device"])[0]
    device_type = query.get("device_type", ["unknown"])[0]
    platform = query.get("platform", ["unknown"])[0]
    browser = query.get("browser", ["Flutter"])[0]

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

            # Captura o IP do cliente
            ip_address = None
            if 'HTTP_X_FORWARDED_FOR' in environ:
                ip_address = environ['HTTP_X_FORWARDED_FOR'].split(',')[0].strip()
            elif 'REMOTE_ADDR' in environ:
                ip_address = environ['REMOTE_ADDR']

            # Lógica de limite de dispositivos (já implementada)
            MAX_DEVICES = 5
            active_sessions = db.query(models.StoreSession).filter(
                models.StoreSession.user_id == admin_id,
                models.StoreSession.client_type == 'admin',
                models.StoreSession.sid != sid
            ).order_by(models.StoreSession.created_at.asc()).all()

            if len(active_sessions) >= MAX_DEVICES:
                oldest_session = active_sessions[0]
                print(f"⚠️ Limite de {MAX_DEVICES} dispositivos atingido. Desconectando: {oldest_session.sid}")

                await self.emit(
                    "session_limit_reached",
                    {
                        "message": f"Você foi desconectado porque o limite de {MAX_DEVICES} dispositivos foi atingido.",
                        "max_devices": MAX_DEVICES
                    },
                    to=oldest_session.sid
                )

                await sio.disconnect(oldest_session.sid, namespace='/admin')
                db.delete(oldest_session)
                db.commit()

            print(f"✅ Dispositivos ativos para admin {admin_id}: {len(active_sessions)} de {MAX_DEVICES}")

            # Entrar na sala de notificações
            notification_room = f"admin_notifications_{admin_id}"
            await self.enter_room(sid, notification_room)
            print(f"✅ Admin {sid} (ID: {admin_id}) entrou na sala de notificações: {notification_room}")

            # Busca lojas acessíveis
            accessible_store_accesses = StoreAccessService.get_accessible_stores_with_roles(db, admin_user)

            stores_list_payload = []
            for access in accessible_store_accesses:
                # ✅ RETORNA SCHEMA JÁ VALIDADO
                store_with_role = StoreTransformerService.enrich_store_access_with_role(
                    store_access=access,
                    db=db
                )
                stores_list_payload.append(store_with_role.model_dump(mode='json'))

            await self.emit("admin_stores_list", {"stores": stores_list_payload}, to=sid)

            if not stores_list_payload:
                await self.emit("user_has_no_stores", {
                    "user_id": admin_id,
                    "message": "Você não possui lojas."
                }, to=sid)

            all_accessible_store_ids = [access.store_id for access in accessible_store_accesses]
            default_store_id = all_accessible_store_ids[0] if all_accessible_store_ids else None

            # ✅ NOVO: Cria sessão com informações do dispositivo
            SessionService.create_or_update_session(
                db,
                sid=sid,
                user_id=admin_id,
                store_id=default_store_id,
                client_type="admin",
                device_name=device_name,
                device_type=device_type,
                platform=platform,
                browser=browser,
                ip_address=ip_address
            )

            print(f"🎯 Conexão do admin {admin_id} (SID: {sid}) finalizada. Dispositivo: {device_name} ({platform})")

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
                print(f"ℹ️ Nenhuma session encontrada para SID {sid}")

            self.environ.pop(sid, None)
            print(f"✅ Environ limpo para SID {sid}")

        except Exception as e:
            print(f"❌ Erro na desconexão do SID {sid}: {str(e)}")
            db.rollback()
            try:
                self.environ.pop(sid, None)
            except:
                pass