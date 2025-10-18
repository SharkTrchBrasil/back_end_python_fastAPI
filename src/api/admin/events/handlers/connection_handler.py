import time
from collections import defaultdict
from urllib.parse import parse_qs

from src.api.admin.services.store_access_service import StoreAccessService
from src.api.admin.services.store_session_service import SessionService
from src.api.admin.services.subscription_service import SubscriptionService
from src.api.schemas.store.store_with_role import StoreWithRole
from src.core import models
from src.core.database import get_db_manager
from src.socketio_instance import sio
from src.api.admin.utils.authorize_admin import authorize_admin_by_jwt

# ✅ Importar logger correto
import logging

logger = logging.getLogger(__name__)

# ✅ Rate limiting para WebSocket
connection_attempts = defaultdict(list)
MAX_CONNECTIONS_PER_MINUTE = 10


async def handle_admin_connect(self, sid, environ):
    """
    Manipulador de conexão do admin com rate limiting
    """
    print(f"[ADMIN] Tentativa de conexão: {sid}")

    # ═══════════════════════════════════════════════════════════
    # 1. EXTRAÇÃO DE PARÂMETROS
    # ═══════════════════════════════════════════════════════════

    query = parse_qs(environ.get("QUERY_STRING", ""))
    token = query.get("admin_token", [None])[0]

    # Captura informações do dispositivo
    device_name = query.get("device_name", ["Unknown Device"])[0]
    device_type = query.get("device_type", ["unknown"])[0]
    platform = query.get("platform", ["unknown"])[0]
    browser = query.get("browser", ["Flutter"])[0]

    if not token:
        raise ConnectionRefusedError("Token obrigatório")

    # ═══════════════════════════════════════════════════════════
    # 2. RATE LIMITING POR IP
    # ═══════════════════════════════════════════════════════════

    # Captura IP do cliente (considera proxy/Railway)
    if 'HTTP_X_FORWARDED_FOR' in environ:
        client_ip = environ['HTTP_X_FORWARDED_FOR'].split(',')[0].strip()
    elif 'REMOTE_ADDR' in environ:
        client_ip = environ['REMOTE_ADDR']
    else:
        client_ip = "unknown"

    current_time = time.time()

    # Limpa tentativas antigas (mais de 1 minuto)
    connection_attempts[client_ip] = [
        t for t in connection_attempts[client_ip]
        if current_time - t < 60
    ]

    # Verifica se excedeu limite
    if len(connection_attempts[client_ip]) >= MAX_CONNECTIONS_PER_MINUTE:
        logger.warning(
            f"🚨 RATE LIMIT WEBSOCKET EXCEDIDO\n"
            f"   ├─ IP: {client_ip}\n"
            f"   ├─ Tentativas: {len(connection_attempts[client_ip])}\n"
            f"   └─ Limite: {MAX_CONNECTIONS_PER_MINUTE}/minuto"
        )
        raise ConnectionRefusedError("Muitas tentativas de conexão. Aguarde 1 minuto.")

    # Registra esta tentativa
    connection_attempts[client_ip].append(current_time)

    # ═══════════════════════════════════════════════════════════
    # 3. AUTENTICAÇÃO E PROCESSAMENTO
    # ═══════════════════════════════════════════════════════════

    self.environ[sid] = environ

    with get_db_manager() as db:
        try:
            # Valida JWT
            admin_user = await authorize_admin_by_jwt(db, token)

            if not admin_user or not admin_user.id:
                raise ConnectionRefusedError("Acesso negado: Admin inválido.")

            admin_id = admin_user.id
            logger.info(f"✅ Admin {admin_user.email} (ID: {admin_id}) autenticado com sucesso.")

            # ═══════════════════════════════════════════════════════════
            # 4. LIMITE DE DISPOSITIVOS (MAX 5 DISPOSITIVOS)
            # ═══════════════════════════════════════════════════════════

            MAX_DEVICES = 5
            active_sessions = db.query(models.StoreSession).filter(
                models.StoreSession.user_id == admin_id,
                models.StoreSession.client_type == 'admin',
                models.StoreSession.sid != sid
            ).order_by(models.StoreSession.created_at.asc()).all()

            if len(active_sessions) >= MAX_DEVICES:
                oldest_session = active_sessions[0]
                logger.warning(
                    f"⚠️ Limite de {MAX_DEVICES} dispositivos atingido para admin {admin_id}. "
                    f"Desconectando dispositivo mais antigo: {oldest_session.sid}"
                )

                # Notifica dispositivo que será desconectado
                await self.emit(
                    "session_limit_reached",
                    {
                        "message": f"Você foi desconectado porque o limite de {MAX_DEVICES} dispositivos foi atingido.",
                        "max_devices": MAX_DEVICES
                    },
                    to=oldest_session.sid
                )

                # Desconecta e remove sessão antiga
                await sio.disconnect(oldest_session.sid, namespace='/admin')
                db.delete(oldest_session)
                db.commit()

            logger.info(f"✅ Dispositivos ativos para admin {admin_id}: {len(active_sessions)}/{MAX_DEVICES}")

            # ═══════════════════════════════════════════════════════════
            # 5. SALA DE NOTIFICAÇÕES
            # ═══════════════════════════════════════════════════════════

            notification_room = f"admin_notifications_{admin_id}"
            await self.enter_room(sid, notification_room)
            logger.info(f"✅ Admin {sid} entrou na sala de notificações: {notification_room}")

            # ═══════════════════════════════════════════════════════════
            # 6. BUSCA LOJAS ACESSÍVEIS
            # ═══════════════════════════════════════════════════════════

            accessible_store_accesses = StoreAccessService.get_accessible_stores_with_roles(db, admin_user)

            stores_list_payload = []
            for access in accessible_store_accesses:
                # Obtém dados da loja com subscription
                store_dict = SubscriptionService.get_store_dict_with_subscription(
                    store=access.store,
                    db=db
                )

                access_dict = {
                    'store': store_dict,
                    'role': access.role,
                    'store_id': access.store_id,
                    'user_id': access.user_id,
                }

                store_with_role = StoreWithRole.model_validate(access_dict)
                stores_list_payload.append(store_with_role.model_dump(mode='json'))

            # Envia lista de lojas para o cliente
            await self.emit("admin_stores_list", {"stores": stores_list_payload}, to=sid)

            # Se não tiver lojas, notifica
            if not stores_list_payload:
                await self.emit("user_has_no_stores", {
                    "user_id": admin_id,
                    "message": "Você não possui lojas."
                }, to=sid)

            # ═══════════════════════════════════════════════════════════
            # 7. CRIA SESSÃO NO BANCO
            # ═══════════════════════════════════════════════════════════

            all_accessible_store_ids = [access.store_id for access in accessible_store_accesses]
            default_store_id = all_accessible_store_ids[0] if all_accessible_store_ids else None

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
                ip_address=client_ip
            )

            logger.info(
                f"🎯 Conexão concluída: Admin {admin_id} (SID: {sid}) | "
                f"Dispositivo: {device_name} ({platform})"
            )

        except ConnectionRefusedError:
            # Re-lança erros de conexão recusada
            raise

        except Exception as e:
            db.rollback()
            logger.error(f"❌ Erro ao processar conexão do admin (SID: {sid}): {str(e)}", exc_info=True)
            self.environ.pop(sid, None)
            raise ConnectionRefusedError(f"Falha na autenticação: {str(e)}")


async def handle_admin_disconnect(self, sid):
    """
    Manipulador de desconexão do admin
    """
    logger.info(f"[ADMIN] Desconexão: {sid}")

    with get_db_manager() as db:
        try:
            # Remove sessão do banco
            session = db.query(models.StoreSession).filter_by(sid=sid).first()

            if session:
                db.delete(session)
                db.commit()
                logger.info(f"✅ Sessão removida: {sid}")
            else:
                logger.info(f"ℹ️ Nenhuma sessão encontrada para: {sid}")

            # Limpa environ
            self.environ.pop(sid, None)
            logger.info(f"✅ Environ limpo para: {sid}")

        except Exception as e:
            logger.error(f"❌ Erro na desconexão (SID: {sid}): {str(e)}", exc_info=True)
            db.rollback()

            # Tenta limpar environ mesmo com erro
            try:
                self.environ.pop(sid, None)
            except:
                pass