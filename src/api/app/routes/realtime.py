from datetime import datetime
from urllib.parse import parse_qs

import socketio
from pydantic import ValidationError
from sqlalchemy.orm import joinedload

from src.api.admin.services.order_code import generate_unique_public_id, gerar_sequencial_do_dia
from src.api.app.routes import products
from src.api.app.schemas.new_order import NewOrder
from src.api.app.schemas.store_details import StoreDetails
from src.api.app.services.rating import (
    get_store_ratings_summary,
    get_product_ratings_summary,
)
from src.api.shared_schemas.product import ProductOut
from src.api.shared_schemas.rating import RatingsSummaryOut
from src.api.shared_schemas.store_theme import StoreThemeOut

from src.core import models
from src.core.database import get_db_manager
from dateutil import parser
from src.api.app.services import payment as payment_services
from src.api.app.schemas.order import Order
from src.socketio_instance import sio


async def refresh_product_list(db, store_id: int, sid: str | None = None):
    products_l = db.query(models.Product).options(
        joinedload(models.Product.variant_links)
        .joinedload(models.ProductVariantProduct.variant)
        .joinedload(models.Variant.options)
    ).filter_by(store_id=store_id, available=True).all()

    # Pega avaliações dos produtos
    product_ratings = {
        product.id: get_product_ratings_summary(db, product_id=product.id)
        for product in products_l
    }

    # Junta dados do produto + avaliações
    payload = [
        {
            **ProductOut.from_orm_obj(product).model_dump(exclude_unset=True),
            "rating": product_ratings.get(product.id),
        }
        for product in products_l
    ]

    target = sid if sid else f"store_{store_id}"
    await sio.emit("products_updated", payload, to=target)


# Evento de conexão do Socket.IO
@sio.event
async def connect(sid, environ):
    query = parse_qs(environ.get("QUERY_STRING", ""))
    token = query.get("totem_token", [None])[0]

    if not token:
        raise ConnectionRefusedError("Missing token")

    with get_db_manager() as db:
        totem = db.query(models.TotemAuthorization).filter(
            models.TotemAuthorization.totem_token == token,
            models.TotemAuthorization.granted.is_(True),
        ).first()

        if not totem or not totem.store:
            raise ConnectionRefusedError("Invalid or unauthorized token")

        # Atualiza o SID do totem
        totem.sid = sid
        db.commit()

        room_name = f"store_{totem.store_id}"
        await sio.enter_room(sid, room_name)

        # Carrega dados completos da loja com seus relacionamentos
        # Loja -> delivery_config
        # Loja -> Cidades -> Bairros
        store = db.query(models.Store).options(
            joinedload(models.Store.payment_methods),
            joinedload(models.Store.delivery_config),  # Carrega a configuração de entrega (sem cidades/bairros aqui)
            joinedload(models.Store.hours),
            # Carrega as cidades da loja e, para cada cidade, seus bairros
          #  joinedload(models.Store.cities).joinedload(models.StoreCity.neighborhoods),
        ).filter_by(id=totem.store_id).first()

        if store:
            # Envia dados da loja com avaliações
            try:
                # Converte o objeto SQLAlchemy 'store' para o Pydantic 'StoreDetails'
                store_schema = StoreDetails.model_validate(store)
            except Exception as e:
                print(f"Erro ao validar Store com Pydantic StoreDetails para loja {store.id}: {e}")
                # Isso pode indicar que StoreDetails ou seus aninhados (StoreCity Pydantic, StoreNeighborhood Pydantic)
                # não estão configurados corretamente com model_config = {"from_attributes": True, "arbitrary_types_allowed": True}
                raise ConnectionRefusedError(f"Erro interno do servidor: Dados da loja malformados: {e}")

            store_schema.ratingsSummary = RatingsSummaryOut(
                **get_store_ratings_summary(db, store_id=store.id)
            )
            # Converte o modelo Pydantic para um dicionário serializável para JSON
            store_payload = store_schema.model_dump()
            await sio.emit("store_updated", store_payload, to=sid)

            # Envia tema
            theme = db.query(models.StoreTheme).filter_by(store_id=totem.store_id).first()
            if theme:
                await sio.emit(
                    "theme_updated",
                    StoreThemeOut.model_validate(theme).model_dump(),
                    to=sid,
                )

            # Envia lista de produtos
            await refresh_product_list(db, totem.store_id, sid)

            # Envia os banners da loja
            banners = db.query(models.Banner).filter_by(store_id=totem.store_id).all()
            if banners:
                from src.api.shared_schemas.banner import BannerOut

                banner_payload = [BannerOut.model_validate(b).model_dump() for b in banners]
                await sio.emit("banners_updated", banner_payload, to=sid)


# Evento de desconexão do Socket.IO
@sio.event
async def disconnect(sid, reason):
    print("disconnect", sid, reason)

    with get_db_manager() as db:
        totem = db.query(models.TotemAuthorization).filter_by(sid=sid).first()
        if totem:
            await sio.leave_room(sid, f"store_{totem.store_id}")
            totem.sid = None
            db.commit()


@sio.event
async def send_order(sid, data): # This is the corrected signature
    print('[SOCKET] Evento send_order recebido')
    print('[SOCKET] sid:', sid)
    print('[SOCKET] data:', data)

    with get_db_manager() as db:
        totem = db.query(models.TotemAuthorization).filter(models.TotemAuthorization.sid == sid).first()
        if not totem:
            # Instead of await callback({...}), simply return the dictionary
            return {'error': 'Totem não encontrado ou não autorizado'}

        # pix_config = db.query(models.StorePixConfig).filter_by(store_id=totem.store_id).first()
        # if not pix_config:
        #     return {'error': 'Configuração Pix não encontrada para a loja'}

        try:
            new_order = NewOrder(**data)
        except ValidationError as e:
            print(f"[SOCKET] Erro de validação do pedido: {e.errors()}")
            return {'error': 'Dados do pedido inválidos', 'details': e.errors()}

        # Buscar o cliente apenas pelo ID, pois ele não está vinculado a uma loja específica
        customer = db.query(models.Customer).filter_by(id=new_order.customer_id).first()

        if not customer:
            # Se o cliente não for encontrado, retorne um erro apropriado
            return {'error': 'Cliente não encontrado'}


        address_id_to_use = None
        if new_order.address:  # Se new_order.address não for None
            address_id_to_use = new_order.address.id

        try:
            db_order = models.Order(
                sequential_id=gerar_sequencial_do_dia(db, totem.store_id),
                public_id=generate_unique_public_id(db, totem.store_id),
                store_id=totem.store_id,
                totem_id=totem.id,
                customer_id=new_order.customer_id,
                payment_method_id=new_order.payment_method_id,

                address_id=address_id_to_use,
                order_type='cardapio_digital',
                delivery_type=new_order.delivery_type,
                payment_status='pendent',
                order_status='pendent',
                needs_change=new_order.needs_change,
                change_for=new_order.change_for,
                observation=new_order.observation,
                delivery_fee=new_order.delivery_fee,
            )

            products = db.query(models.Product).filter(
                models.Product.store_id == totem.store_id,
                models.Product.id.in_([p.product_id for p in new_order.products])
            ).all()

            total_price_calculated = 0

            for order_product in new_order.products:
                product = next(p for p in products if p.id == order_product.product_id)
                calculated_price = product.base_price
                if calculated_price != order_product.price:
                    return {'error': f"Preço inválido para o produto {product.name}"}

                db_product = models.OrderProduct(
                    store_id=totem.store_id,
                    product_id=product.id,
                    name=product.name,
                    price=calculated_price,
                    quantity=order_product.quantity,
                    note=order_product.note
                )

                db_order.products.append(db_product)

                variants_price = 0
                for order_variant in order_product.variants:
                    variant = next(v for v in product.variants if v.id == order_variant.variant_id)
                    db_variant = models.OrderVariant(
                        order_product=db_product,
                        store_id=totem.store_id,
                        variant_id=variant.id,
                        name=variant.name,
                    )
                    db_product.variants.append(db_variant)

                    options_price = 0
                    for order_option in order_variant.options:
                        option = next(o for o in variant.options if o.id == order_option.variant_option_id)
                        if option.price != order_option.price:
                            return {'error': f"Preço inválido para a opção {option.name} do produto {product.name}"}

                        db_option = models.OrderVariantOption(
                            order_variant=db_variant,
                            store_id=totem.store_id,
                            variant_option_id=option.id,
                            name=option.name,
                            price=option.price,
                            quantity=order_option.quantity
                        )
                        db_variant.options.append(db_option)
                        options_price += db_option.price * order_option.quantity

                    variants_price += options_price

                total_price_calculated += (calculated_price + variants_price) * order_product.quantity

            if new_order.delivery_fee:
                total_price_calculated += new_order.delivery_fee

            if new_order.total_price != total_price_calculated:
                return {'error': f"Total incorreto. Esperado: {total_price_calculated}, recebido: {new_order.total_price}"}

            db_order.total_price = total_price_calculated

            db.add(db_order)
            db.commit()

            order_dict = Order.model_validate(db_order).model_dump()
            print('[SOCKET] Pedido processado com sucesso e retornado ao cliente')
            return {'success': True, 'order': order_dict} # Return the success message

        except Exception as e:
            db.rollback()
            print(f"[SOCKET] Erro ao processar o pedido: {e}")
            return {'error': f"Erro ao processar o pedido: {str(e)}"} # Return the error message