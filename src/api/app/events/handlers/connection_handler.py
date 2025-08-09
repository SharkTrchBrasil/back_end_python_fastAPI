# Em: src/api/app/events/totem_namespace.py

from socketio import AsyncNamespace
from urllib.parse import parse_qs
from datetime import datetime
from fastapi.encoders import jsonable_encoder
from sqlalchemy.orm import selectinload, joinedload

from src.api.app.events.socketio_emitters import _prepare_products_payload
# --- Imports dos seus Módulos e Serviços ---
from src.core import models
from src.core.database import get_db_manager
from src.api.app.services.authorize_totem import authorize_totem
from src.api.app.services.rating import get_store_ratings_summary
from src.api.admin.services.subscription_service import SubscriptionService  # ✅ Reutilizamos o serviço!

from src.api.schemas.rating import RatingsSummaryOut
from src.api.schemas.store_details import StoreDetails



async def handler_totem_on_connect(self, sid, environ):
    print(f"🔌 [TOTEM] Conexão recebida. SID: {sid}")
    query = parse_qs(environ.get("QUERY_STRING", ""))
    token = query.get("totem_token", [None])[0]

    if not token:
        print(f"❌ [TOTEM] Conexão {sid} recusada: Token ausente.")
        raise ConnectionRefusedError("Missing token")

    with get_db_manager() as db:
        try:
            # 1. Autorização
            totem = await authorize_totem(db, token)
            if not totem or not totem.store:
                print(f"❌ [TOTEM] Conexão {sid} recusada: Token inválido.")
                raise ConnectionRefusedError("Invalid or unauthorized token")

            store_id = totem.store.id
            print(f"🏪 [TOTEM] {sid} autorizado para a loja: {store_id}")

            # 2. Sessão e Sala do Socket.IO
            session = models.StoreSession(sid=sid, store_id=store_id, client_type='totem')
            db.add(session)
            db.commit()
            await self.enter_room(sid, f"store_{store_id}")

            # 3. Carregar TODOS os dados da loja com a "Super Consulta"
            store = db.query(models.Store).options(
                selectinload(models.Store.payment_activations).selectinload(
                    models.StorePaymentMethodActivation.platform_method),
                joinedload(models.Store.store_operation_config),
                selectinload(models.Store.hours),
                selectinload(models.Store.cities).selectinload(models.StoreCity.neighborhoods),
                selectinload(models.Store.coupons),
                selectinload(models.Store.products).selectinload(models.Product.category),
                selectinload(models.Store.products).selectinload(models.Product.variant_links).selectinload(
                    models.ProductVariantLink.variant).selectinload(models.Variant.options).selectinload(
                    models.VariantOption.linked_product),
                selectinload(models.Store.variants).selectinload(models.Variant.options),
                selectinload(models.Store.subscriptions).joinedload(models.StoreSubscription.plan)
            ).filter(models.Store.id == store_id).first()

            if not store:
                raise ConnectionRefusedError(f"Loja {store_id} não encontrada.")

            # 4. Determinar o Status Operacional usando o Serviço Centralizado
            _, is_operational = SubscriptionService.get_subscription_details(store)
            print(
                f"🚦 [TOTEM] Status operacional da loja {store_id}: {'PODE OPERAR' if is_operational else 'BLOQUEADA'}")

            # 5. Montar o Payload para o Totem
            store_schema = StoreDetails.model_validate(store)
            store_schema.ratingsSummary = RatingsSummaryOut(**get_store_ratings_summary(db, store_id=store.id))

            # Adiciona a flag operacional ao payload final
            if store_schema.store_operation_config:
                store_schema.store_operation_config.is_operational = is_operational

            initial_state_payload = {
                "store": store_schema,
                "theme": store.theme,
                "products": _prepare_products_payload(db, store.products),
                "banners": store.banners
            }

            # 6. Enviar o estado inicial para o Totem
            await self.emit("initial_state_loaded", jsonable_encoder(initial_state_payload), to=sid)
            print(f"✅ [TOTEM] Estado inicial enviado com sucesso para {sid}")

        except Exception as e:
            db.rollback()
            print(f"❌ [TOTEM] Erro crítico na conexão {sid}: {e.__class__.__name__}: {str(e)}")
            raise ConnectionRefusedError(str(e))

async def handler_totem_on_disconnect(self, sid):
    print(f"🔌 [TOTEM] Cliente desconectado: {sid}")
    with get_db_manager() as db:
        try:
            session = db.query(models.StoreSession).filter_by(sid=sid, client_type='totem').first()
            if session:
                await self.leave_room(sid, f"store_{session.store_id}")
                db.delete(session)
                db.commit()
        except Exception as e:
            db.rollback()
            print(f"❌ Erro na desconexão do totem {sid}: {str(e)}")