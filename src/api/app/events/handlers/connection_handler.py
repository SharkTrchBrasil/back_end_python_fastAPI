# src/api/app/events/handlers/connection_handler.py

from urllib.parse import parse_qs
from fastapi.encoders import jsonable_encoder

from src.api.crud import store_crud
from src.core import models
from src.core.database import get_db_manager
from src.api.app.services.authorize_totem import authorize_totem
from src.api.app.services.rating import get_store_ratings_summary, get_product_ratings_summary
from src.api.admin.services.subscription_service import SubscriptionService
from src.api.schemas.products.rating import RatingsSummaryOut
from src.api.schemas.store.store_details import StoreDetails



async def handler_totem_on_connect(self, sid, environ):
    print(f"🔌 [TOTEM] Conexão recebida. SID: {sid}")
    query = parse_qs(environ.get("QUERY_STRING", ""))
    token = query.get("totem_token", [None])[0]

    if not token:
        print(f"❌ [TOTEM] Conexão {sid} recusada: Token ausente.")
        raise ConnectionRefusedError("Missing token")

    with get_db_manager() as db:
        try:
            totem_auth = await authorize_totem(db, token)
            if not totem_auth or not totem_auth.store_id:
                print(f"❌ [CONEXÃO] {sid} recusada: Token inválido ou não autorizado.")
                raise ConnectionRefusedError("Invalid or unauthorized token.")

            store_id = totem_auth.store_id
            print(f"🏪 [CONEXÃO] {sid} autorizado para a loja: {store_id}")

            customer_session = models.CustomerSession(sid=sid, store_id=store_id, customer_id=None)
            db.add(customer_session)
            db.commit()

            await self.enter_room(sid, f"store_{store_id}")
            print(f"🚪 [CONEXÃO] {sid} adicionado à sala da loja {store_id}.")

            store = store_crud.get_store_for_customer_view(db=db, store_id=store_id)
            if not store:
                raise ConnectionRefusedError(f"Loja {store_id} não encontrada.")

            product_ratings = {
                p.id: get_product_ratings_summary(db, product_id=p.id)
                for p in store.products
            }
            for product in store.products:
                product.rating = product_ratings.get(product.id)

            # ✅ DEBUG: Captura e analisa o retorno
            result = SubscriptionService.get_subscription_details(store)
            print(f"🔍 [DEBUG] get_subscription_details retornou: {result}")
            print(f"🔍 [DEBUG] Tipo: {type(result)}, Quantidade: {len(result) if isinstance(result, tuple) else 'não é tupla'}")

            # Desempacota baseado no resultado
            if isinstance(result, tuple):
                if len(result) == 4:
                    subscription_data, is_blocked, warning_message, _ = result
                elif len(result) == 3:
                    is_blocked, warning_message, _ = result
                elif len(result) == 2:
                    is_blocked, warning_message = result
                else:
                    print(f"❌ [DEBUG] Formato inesperado: {len(result)} valores")
                    is_blocked = True
                    warning_message = "Erro de formato"
            else:
                is_blocked = True
                warning_message = "Retorno não é tupla"

            is_operational = not is_blocked

            if is_blocked:
                print(f"⚠️ [TOTEM] Loja {store_id} BLOQUEADA: {warning_message}")

            store_schema = StoreDetails.model_validate(store)
            store_schema.ratingsSummary = RatingsSummaryOut(
                **get_store_ratings_summary(db, store_id=store.id)
            )

            if store_schema.store_operation_config:
                store_schema.store_operation_config.is_operational = is_operational

            initial_state_payload = {
                "store": store_schema,
                "theme": store.theme,
                "products": store_schema.products,
                "banners": store.banners
            }

            await self.emit(
                "initial_state_loaded",
                jsonable_encoder(initial_state_payload),
                to=sid
            )
            print(f"✅ [TOTEM] Estado inicial enviado para {sid} (Operacional: {is_operational})")

        except Exception as e:
            db.rollback()
            print(f"❌ [TOTEM] Erro crítico na conexão {sid}: {e.__class__.__name__}: {str(e)}")
            import traceback
            traceback.print_exc()
            raise ConnectionRefusedError(str(e))

async def handler_totem_on_disconnect(self, sid):
    print(f"🔌 [TOTEM] Cliente desconectado: {sid}")
    with get_db_manager() as db:
        try:
            session = db.query(models.CustomerSession).filter_by(sid=sid).first()
            if session:
                await self.leave_room(sid, f"store_{session.store_id}")
                db.delete(session)
                db.commit()
                print(f"✅ [TOTEM] Sessão {sid} removida.")
            else:
                print(f"ℹ️ [TOTEM] Nenhuma sessão encontrada para {sid}")
        except Exception as e:
            db.rollback()
            print(f"❌ Erro na desconexão do totem {sid}: {str(e)}")