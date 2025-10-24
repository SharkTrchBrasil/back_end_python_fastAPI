# src/api/app/events/handlers/connection_handler.py

import traceback
from logging import getLogger
from urllib.parse import parse_qs

from fastapi.encoders import jsonable_encoder
from socketio.exceptions import ConnectionRefusedError

from src.api.admin.services.subscription_service import SubscriptionService
from src.api.app.services.connection_token_service import ConnectionTokenService
from src.api.app.services.rating import get_store_ratings_summary, get_product_ratings_summary
from src.api.crud import store_crud
from src.api.schemas.products.rating import RatingsSummaryOut
from src.api.schemas.store.store_details import StoreDetails
from src.core import models
from src.core.database import get_db_manager

# Configura um logger específico para este módulo para melhor rastreabilidade
logger = getLogger(__name__)


async def handler_totem_on_connect(self, sid, environ):
    """
    Handler robusto e seguro para novas conexões de totens (clientes do cardápio).
    Valida um token de conexão de uso único e curta duração.
    """
    logger.info(f"🔌 [CONEXÃO] Nova tentativa de conexão recebida. SID: {sid}")

    query = parse_qs(environ.get("QUERY_STRING", ""))

    # 1. Espera o `connection_token` de uso único, não mais o totem_token persistente.
    connection_token = query.get("connection_token", [None])[0]

    if not connection_token:
        logger.warning(f"❌ [CONEXÃO] {sid} recusada: `connection_token` ausente na query.")
        raise ConnectionRefusedError("Connection token missing")

    # Usa um gerenciador de contexto para garantir que a sessão do banco seja fechada.
    with get_db_manager() as db:
        try:
            # 2. Valida e consome o token de uso único.
            # Esta é a etapa de autorização principal para o WebSocket.
            totem_auth = ConnectionTokenService.validate_and_consume_token(db, connection_token)

            if not totem_auth:
                logger.warning(f"❌ [CONEXÃO] {sid} recusada: Token de conexão inválido, expirado ou já utilizado.")
                raise ConnectionRefusedError("Invalid, expired, or used connection token.")

            store_id = totem_auth.store_id
            logger.info(f"🏪 [CONEXÃO] {sid} autorizado com sucesso para a loja ID: {store_id}")

            # 3. Cria a sessão do cliente no banco de dados.
            # Esta sessão é vinculada ao SID e à loja, começando como anônima.
            customer_session = models.CustomerSession(sid=sid, store_id=store_id, customer_id=None)
            db.add(customer_session)
            db.commit()
            logger.info(f"📝 [SESSÃO] CustomerSession criada para o SID {sid} na loja {store_id}.")

            # 4. Adiciona o cliente a uma "sala" específica da loja.
            # Isso permite enviar eventos para todos os totens de uma mesma loja.
            await self.enter_room(sid, f"store_{store_id}")
            logger.info(f"🚪 [SALA] SID {sid} adicionado à sala 'store_{store_id}'.")

            # 5. Busca todos os dados necessários para o estado inicial do totem.
            logger.info(f"⏳ [DADOS] Buscando estado inicial para a loja {store_id}...")
            store = store_crud.get_store_for_customer_view(db=db, store_id=store_id)
            if not store:
                # Caso raro onde a loja foi deletada entre a autorização e agora.
                logger.error(f"❌ [DADOS] Loja {store_id} não encontrada no banco após autorização bem-sucedida.")
                raise ConnectionRefusedError(f"Store {store_id} not found.")

            # 6. Verifica o status da assinatura da loja.
            subscription_details = SubscriptionService.get_subscription_details(store, db)
            is_blocked = subscription_details.get('is_blocked', True)
            is_operational = not is_blocked

            if is_blocked:
                logger.warning(
                    f"⚠️ [STATUS] Loja {store_id} está BLOQUEADA: {subscription_details.get('warning_message')}")
            else:
                logger.info(
                    f"✅ [STATUS] Loja {store_id} está OPERACIONAL (Status Assinatura: {subscription_details.get('status')})")

            # 7. Monta o payload completo com todos os dados para o cliente.
            store_schema = StoreDetails.model_validate(store)
            store_schema.ratingsSummary = RatingsSummaryOut(**get_store_ratings_summary(db, store_id=store.id))
            if store_schema.store_operation_config:
                store_schema.store_operation_config.is_operational = is_operational

            # Anexa as avaliações aos produtos
            product_ratings = {p.id: get_product_ratings_summary(db, product_id=p.id) for p in store.products}
            for product in store_schema.products:
                product.rating = product_ratings.get(product.id)

            initial_state_payload = {
                "store": store_schema,
                "theme": store.theme,
                "products": store_schema.products,
                "banners": store.banners
            }

            # 8. Envia o estado inicial para o cliente recém-conectado.
            await self.emit(
                "initial_state_loaded",
                jsonable_encoder(initial_state_payload),
                to=sid
            )
            logger.info(f"🚀 [PAYLOAD] Estado inicial enviado com sucesso para o SID {sid}.")

        except ConnectionRefusedError as cre:
            # Re-lança a exceção de recusa de conexão para que o Socket.IO a manipule.
            raise cre
        except Exception as e:
            # Captura qualquer outro erro inesperado, faz rollback e loga.
            db.rollback()
            logger.error(
                f"❌ [ERRO CRÍTICO] Erro inesperado durante a conexão do SID {sid}: {e.__class__.__name__}: {e}")
            logger.error(traceback.format_exc())
            # Recusa a conexão para evitar estados inconsistentes.
            raise ConnectionRefusedError("Internal server error during connection setup.")


async def handler_totem_on_disconnect(self, sid):
    """
    Handler para quando um cliente se desconecta.
    Limpa a sessão do cliente do banco de dados.
    """
    logger.info(f"🔌 [DESCONEXÃO] Cliente desconectado: {sid}")
    with get_db_manager() as db:
        try:
            session = db.query(models.CustomerSession).filter_by(sid=sid).first()
            if session:
                # Remove o cliente da sala da loja.
                await self.leave_room(sid, f"store_{session.store_id}")
                # Deleta o registro da sessão.
                db.delete(session)
                db.commit()
                logger.info(f"✅ [SESSÃO] Sessão {sid} da loja {session.store_id} removida com sucesso.")
            else:
                logger.info(
                    f"ℹ️ [SESSÃO] Nenhuma CustomerSession encontrada para o SID {sid} ao desconectar (pode já ter sido limpa).")
        except Exception as e:
            db.rollback()
            logger.error(f"❌ [ERRO CRÍTICO] Erro na desconexão do SID {sid}: {e}")

