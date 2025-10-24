# src/api/app/events/handlers/connection_handler.py

import traceback
from logging import getLogger
from urllib.parse import parse_qs

from fastapi.encoders import jsonable_encoder
from socketio.exceptions import ConnectionRefusedError

from src.api.admin.services.store_service import StoreService
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
    """
    logger.info(f"🔌 [CONEXÃO] Nova tentativa de conexão recebida. SID: {sid}")

    query = parse_qs(environ.get("QUERY_STRING", ""))
    connection_token = query.get("connection_token", [None])[0]

    if not connection_token:
        logger.warning(f"❌ [CONEXÃO] {sid} recusada: `connection_token` ausente na query.")
        raise ConnectionRefusedError("Connection token missing")

    with get_db_manager() as db:
        try:
            totem_auth = ConnectionTokenService.validate_and_consume_token(db, connection_token)

            if not totem_auth:
                logger.warning(f"❌ [CONEXÃO] {sid} recusada: Token de conexão inválido, expirado ou já utilizado.")
                raise ConnectionRefusedError("Invalid, expired, or used connection token.")

            store_id = totem_auth.store_id
            logger.info(f"🏪 [CONEXÃO] {sid} autorizado com sucesso para a loja ID: {store_id}")

            customer_session = models.CustomerSession(sid=sid, store_id=store_id, customer_id=None)
            db.add(customer_session)
            db.commit()
            logger.info(f"📝 [SESSÃO] CustomerSession criada para o SID {sid} na loja {store_id}.")

            await self.enter_room(sid, f"store_{store_id}")
            logger.info(f"🚪 [SALA] SID {sid} adicionado à sala 'store_{store_id}'.")

            logger.info(f"⏳ [DADOS] Buscando estado inicial para a loja {store_id}...")
            store = store_crud.get_store_for_customer_view(db=db, store_id=store_id)
            if not store:
                logger.error(f"❌ [DADOS] Loja {store_id} não encontrada no banco após autorização bem-sucedida.")
                raise ConnectionRefusedError(f"Store {store_id} not found.")

            # ═══════════════════════════════════════════════════════════════════════════
            # ✅ USA O MESMO SERVIÇO DO ADMIN - DRY (Don't Repeat Yourself)
            # ═══════════════════════════════════════════════════════════════════════════

            logger.info(f"🔍 [DEBUG] Buscando subscription details...")
            subscription_details = SubscriptionService.get_enriched_subscription(store, db)

            if not subscription_details:
                logger.error(f"❌ [ASSINATURA] Não foi possível obter os detalhes da assinatura para a loja {store_id}.")
                raise ConnectionRefusedError("Subscription details not found.")

            logger.info(
                f"✅ [DEBUG] Subscription obtida: status={subscription_details.get('status')}, is_blocked={subscription_details.get('is_blocked')}")

            # ✅ USA O STORESERVICE PARA MONTAR O PAYLOAD (igual ao admin)
            logger.info(f"🔍 [DEBUG] Montando payload completo da loja com StoreService...")
            store_dict = StoreService.get_store_complete_payload(store=store, db=db)
            logger.info(f"✅ [DEBUG] Payload montado com sucesso")

            # ✅ CONVERTE DICT PARA SCHEMA (mas ainda é mutável como dict)
            # NÃO convertemos para Pydantic ainda, mantemos como dict para poder modificar
            logger.info(f"✅ [DEBUG] Payload em formato dict")

            # ✅ ADICIONA RATINGS DA LOJA
            store_ratings = get_store_ratings_summary(db, store_id=store.id)
            store_dict['ratingsSummary'] = store_ratings

            # ✅ ADICIONA RATINGS DOS PRODUTOS (modifica o dict antes de validar)
            logger.info(f"🔍 [DEBUG] Adicionando ratings dos produtos...")
            product_ratings = {p.id: get_product_ratings_summary(db, product_id=p.id) for p in store.products}

            # Modifica os produtos no dict (não no schema Pydantic)
            if 'products' in store_dict and store_dict['products']:
                for product_dict in store_dict['products']:
                    if isinstance(product_dict, dict):
                        product_dict['rating'] = product_ratings.get(product_dict.get('id'))

            logger.info(f"✅ [DEBUG] Ratings dos produtos adicionados")

            # ✅ AGORA VALIDA COM PYDANTIC (depois de adicionar os ratings)
            logger.info(f"🔍 [DEBUG] Validando store_dict com Pydantic...")
            store_schema = StoreDetails.model_validate(store_dict)
            logger.info(f"✅ [DEBUG] Validação Pydantic concluída")

            # ✅ APLICA STATUS OPERACIONAL BASEADO NA ASSINATURA
            is_blocked = subscription_details.get('is_blocked', True)
            is_operational = not is_blocked

            if store_schema.store_operation_config:
                # ✅ CORREÇÃO: Use model_copy para modificar schema imutável
                store_schema.store_operation_config = store_schema.store_operation_config.model_copy(
                    update={'is_operational': is_operational}
                )
                logger.info(f"✅ [STATUS] is_operational definido como: {is_operational}")
            else:
                logger.warning(f"⚠️ [STATUS] store_operation_config é None para loja {store_id}")

            if is_blocked:
                logger.warning(
                    f"⚠️ [STATUS] Loja {store_id} está BLOQUEADA: {subscription_details.get('warning_message')}")
            else:
                logger.info(
                    f"✅ [STATUS] Loja {store_id} está OPERACIONAL (Status: {subscription_details.get('status')})")

            # ✅ MONTA PAYLOAD FINAL
            initial_state_payload = {
                "store": store_schema,
                "theme": store.theme,
                "products": store_schema.products,
                "banners": store.banners
            }

            # ✅ ENVIA PARA O CLIENTE
            await self.emit(
                "initial_state_loaded",
                jsonable_encoder(initial_state_payload),
                to=sid
            )
            logger.info(f"🚀 [PAYLOAD] Estado inicial enviado com sucesso para o SID {sid}.")

        except ConnectionRefusedError as cre:
            logger.error(f"❌ [CONNECTION REFUSED] SID {sid}: {str(cre)}")
            raise cre
        except Exception as e:
            db.rollback()
            logger.error("=" * 80)
            logger.error(f"❌ [ERRO CRÍTICO] Erro inesperado durante a conexão do SID {sid}")
            logger.error(f"   ├─ Tipo: {e.__class__.__name__}")
            logger.error(f"   ├─ Mensagem: {e}")
            logger.error(f"   └─ Traceback completo:")
            logger.error(traceback.format_exc())
            logger.error("=" * 80)
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