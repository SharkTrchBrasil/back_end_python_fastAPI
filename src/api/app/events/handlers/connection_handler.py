from datetime import datetime
from urllib.parse import parse_qs

from sqlalchemy.orm import selectinload, joinedload

from src.api.app.events.socketio_emitters import _prepare_products_payload
from src.api.app.schemas.store_details_totem import StoreDetailsTotem
from src.api.app.services.authorize_totem import authorize_totem
from src.api.app.services.rating import get_store_ratings_summary
from src.api.shared_schemas.banner import BannerOut
from src.api.shared_schemas.rating import RatingsSummaryOut

from src.api.shared_schemas.store_theme import StoreThemeOut
from src.core import models
from src.core.database import get_db_manager


async def handler_totem_on_connect(self, sid, environ):
    print(f"🔌 Novo cliente conectando... SID: {sid}")
    query = parse_qs(environ.get("QUERY_STRING", ""))
    print(f"📦 Query recebida: {query}")
    token = query.get("totem_token", [None])[0]

    if not token:
        print("❌ Token ausente na conexão!")
        raise ConnectionRefusedError("Missing token")

    print(f"🛡️ Token recebido: {token}")

    with get_db_manager() as db:
        try:
            print("🔍 Autorizando totem...")
            totem = await authorize_totem(db, token)
            print(f"✅ Totem autorizado? {'SIM' if totem else 'NÃO'}")

            if not totem or not totem.store:
                print("❌ Token inválido ou loja não vinculada")
                raise ConnectionRefusedError("Invalid or unauthorized token")

            print(f"🏪 Loja vinculada ao totem: {totem.store.id}")

            # Sessão do totem
            print("🔁 Verificando sessão do totem...")
            session = db.query(models.StoreSession).filter_by(sid=sid).first()
            if not session:
                print("📌 Criando nova sessão...")
                session = models.StoreSession(
                    sid=sid,
                    store_id=totem.store.id,
                    client_type='totem'
                )
                db.add(session)
            else:
                print("♻️ Atualizando sessão existente...")
                session.store_id = totem.store.id
                session.updated_at = datetime.utcnow()

            db.commit()
            print("💾 Sessão salva no banco")

            room_name = f"store_{totem.store.id}"
            print(f"🚪 Entrando na sala: {room_name}")
            await self.enter_room(sid, room_name)
            print(f"✅ Cliente {sid} conectado e entrou na sala {room_name}")

            # SUPER CONSULTA
            print(f"🔍 Carregando estado completo para a loja {totem.store.id}...")
            store = db.query(models.Store).options(
                selectinload(models.Store.payment_activations)
                .selectinload(models.StorePaymentMethodActivation.platform_method)
                .selectinload(models.PlatformPaymentMethod.category)
                .selectinload(models.PaymentMethodCategory.group),
                joinedload(models.Store.store_operation_config),
                # Carrega a configuração de entrega (sem cidades/bairros aqui)
                joinedload(models.Store.hours),
                # Carrega as cidades da loja e, para cada cidade, seus bairros
                #  joinedload(models.Store.cities).joinedload(models.StoreCity.neighborhoods),
            ).filter_by(id=totem.store_id).first()


            # store = db.query(models.Store).options(
            #     selectinload(models.Store.payment_activations)
            #     .selectinload(models.StorePaymentMethodActivation.platform_method)
            #     .selectinload(models.PlatformPaymentMethod.category)
            #     .selectinload(models.PaymentMethodCategory.group),
            #     joinedload(models.Store.store_operation_config),
            #     selectinload(models.Store.hours),
            #     selectinload(models.Store.cities).selectinload(models.StoreCity.neighborhoods),
            #     selectinload(models.Store.coupons),
            #     selectinload(models.Store.products)
            #     .selectinload(models.Product.variant_links)
            #     .selectinload(models.ProductVariantLink.variant)
            #     .selectinload(models.Variant.options)
            #     .selectinload(models.VariantOption.linked_product),
            #     selectinload(models.Store.variants).selectinload(models.Variant.options),
            # ).filter(models.Store.id == totem.store.id).first()

            print(f"📦 Resultado da superconsulta: {'Encontrado' if store else 'NÃO encontrado'}")

            if not store:
                raise ConnectionRefusedError("Store not found after query")

            # Montagem do payload
            print("🧩 Validando loja com Pydantic...")
            store_schema = StoreDetailsTotem.model_validate(store)

            print("📊 Buscando resumo de avaliações...")
            store_schema.ratingsSummary = RatingsSummaryOut(
                **get_store_ratings_summary(db, store_id=store.id)
            )

            print("🛠️ Preparando payload de produtos...")
            products_payload = _prepare_products_payload(db, store.products)

            print("🎨 Validando tema da loja...")
            theme = StoreThemeOut.model_validate(store.theme).model_dump(mode='json') if store.theme else None

            print("🖼️ Validando banners...")
            banners_payload = [
                BannerOut.model_validate(b).model_dump(mode='json')
                for b in store.banners
            ] if store.banners else []

            initial_state_payload = {
                "store": store_schema.model_dump(mode='json'),
                "theme": theme,
                "products": products_payload,
                "banners": banners_payload
            }

            print("📡 Emitindo evento 'initial_state_loaded'...")
            await self.emit("initial_state_loaded", initial_state_payload, to=sid)
            print(f"✅ Estado inicial completo enviado com sucesso para o cliente {sid}")

        except Exception as e:
            db.rollback()
            print(f"❌ Erro na conexão do totem: {str(e)}")
            raise ConnectionRefusedError(str(e))


async def handler_totem_on_disconnect(self, sid):
    print("Totem disconnected", sid)

    with get_db_manager() as db:
        try:
            # Remove a sessão do totem
            session = db.query(models.StoreSession).filter_by(sid=sid, client_type='totem').first()
            if session:
                await self.leave_room(sid, f"store_{session.store_id}")
                db.delete(session)
                db.commit()
                print(f"✅ Totem session removida para sid {sid}")

            # Limpeza adicional (opcional)
            totem = db.query(models.TotemAuthorization).filter_by(sid=sid).first()
            if totem:
                totem.sid = None
                db.commit()

        except Exception as e:
            db.rollback()
            print(f"❌ Erro na desconexão do totem: {str(e)}")