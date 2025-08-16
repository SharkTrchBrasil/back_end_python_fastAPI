# Em: src/api/app/events/totem_namespace.py

from urllib.parse import parse_qs
from fastapi.encoders import jsonable_encoder
from sqlalchemy.orm import selectinload, joinedload

from src.api.admin.utils.payment_method_group import _build_payment_groups_from_activations_simplified
from src.core import models
from src.core.database import get_db_manager
from src.api.app.services.authorize_totem import authorize_totem
from src.api.app.services.rating import get_store_ratings_summary, get_product_ratings_summary
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
            totem_auth = await authorize_totem(db, token)
            if not totem_auth or not totem_auth.store_id:
                print(f"❌ [CONEXÃO] {sid} recusada: Token inválido ou não autorizado.")
                raise ConnectionRefusedError("Invalid or unauthorized token.")

            store_id = totem_auth.store_id
            print(f"🏪 [CONEXÃO] {sid} autorizado para a loja: {store_id}")

            customer_session = models.CustomerSession(
                sid=sid,
                store_id=store_id,
                customer_id=None  # Inicia como anônima
            )
            db.add(customer_session)
            db.commit()

            print(f"👤 [CONEXÃO] Sessão de cliente anônima criada para {sid}.")


            await self.enter_room(sid, f"store_{store_id}")
            print(f"🚪 [CONEXÃO] {sid} adicionado à sala da loja {store_id}.")

            # 3. Carregar TODOS os dados da loja com a "Super Consulta"
            store = db.query(models.Store).options(

                selectinload(models.Store.payment_activations)
                .selectinload(models.StorePaymentMethodActivation.platform_method)
                .selectinload(models.PlatformPaymentMethod.category)
                .selectinload(models.PaymentMethodCategory.group),

                joinedload(models.Store.store_operation_config),
                selectinload(models.Store.hours),
                selectinload(models.Store.cities).selectinload(models.StoreCity.neighborhoods),
                # ✅ MUDANÇA AQUI: Agora também carregamos as regras de cada cupom
                selectinload(models.Store.coupons).selectinload(models.Coupon.rules),

                # ✅ CONSULTA AOS PRODUTOS AGRUPADA E OTIMIZADA
                selectinload(models.Store.products).options(
                    selectinload(models.Product.category),
                    selectinload(models.Product.default_options),  # Carrega as opções padrão
                    selectinload(models.Product.variant_links).selectinload(
                        models.ProductVariantLink.variant).selectinload(
                        models.Variant.options).selectinload(
                        models.VariantOption.linked_product)
                ),

                selectinload(models.Store.variants).selectinload(models.Variant.options),
                selectinload(models.Store.subscriptions).joinedload(models.StoreSubscription.plan)

            ).filter(models.Store.id == store_id).first()

            if not store:
                raise ConnectionRefusedError(f"Loja {store_id} não encontrada.")

            # ✅ NOVO PRÉ-PROCESSAMENTO:
            # 1. Busque todas as avaliações dos produtos da loja de uma vez.
            product_ratings = {
                p.id: get_product_ratings_summary(db, product_id=p.id)
                for p in store.products
            }
            # 2. Anexe as avaliações diretamente aos objetos SQLAlchemy.
            #    O Pydantic lerá esses atributos ao validar.
            for product in store.products:
                product.rating = product_ratings.get(product.id)



            # 4. Determinar o Status Operacional usando o Serviço Centralizado
            _, is_operational = SubscriptionService.get_subscription_details(store)
            print(
                f"🚦 [TOTEM] Status operacional da loja {store_id}: {'PODE OPERAR' if is_operational else 'BLOQUEADA'}")

            # 5. Montar o Payload para o Totem
            store_schema = StoreDetails.model_validate(store)
            store_schema.ratingsSummary = RatingsSummaryOut(**get_store_ratings_summary(db, store_id=store.id))

            # ✅ AQUI ESTÁ A MÁGICA:
            # 1. Chame a função de transformação com as ativações carregadas
            payment_groups_structured = _build_payment_groups_from_activations_simplified(store.payment_activations)

            # 2. Atribua o resultado estruturado diretamente ao schema
            store_schema.payment_method_groups = payment_groups_structured

            # Adiciona a flag operacional ao payload final
            if store_schema.store_operation_config:
                store_schema.store_operation_config.is_operational = is_operational

            initial_state_payload = {
                "store": store_schema,
                "theme": store.theme,
                 "products": store_schema.products,
                "banners": store.banners
            }

            # 6. Enviar o estado inicial para o Totem
            await self.emit("initial_state_loaded", jsonable_encoder(initial_state_payload), to=sid)
            print(f"✅ [TOTEM] Estado inicial enviado com sucesso para {sid}")

        except Exception as e:
            db.rollback()
            print(f"❌ [TOTEM] Erro crítico na conexão {sid}: {e.__class__.__name__}: {str(e)}")
            raise ConnectionRefusedError(str(e))

# ✅ FUNÇÃO DE DESCONEXÃO CORRIGIDA
async def handler_totem_on_disconnect(self, sid):
    print(f"🔌 [TOTEM] Cliente desconectado: {sid}")
    with get_db_manager() as db:
        try:
            # CORREÇÃO: Busca e deleta a 'CustomerSession'
            session = db.query(models.CustomerSession).filter_by(sid=sid).first()
            if session:
                await self.leave_room(sid, f"store_{session.store_id}")
                db.delete(session)
                db.commit()
                print(f"✅ [TOTEM] Sessão de cliente {sid} removida com sucesso.")
        except Exception as e:
            db.rollback()
            print(f"❌ Erro na desconexão do totem {sid}: {str(e)}")