import asyncio
import datetime
from operator import or_
from urllib.parse import parse_qs


import sqlalchemy
from fastapi.encoders import jsonable_encoder
from pydantic import ValidationError
from sqlalchemy.orm import joinedload

from src.api.admin.events.admin_socketio_emitters import emit_order_updated
from src.api.admin.services.order_code import generate_unique_public_id, gerar_sequencial_do_dia
from src.api.app.events.socketio_emitters import refresh_product_list

from src.api.app.schemas.new_order import NewOrder
from src.api.app.schemas.store_details import StoreDetails
from src.api.app.services.add_customer_store import register_customer_store_relationship
from src.api.app.services.check_variants import validate_order_variants

from src.api.app.services.rating import (
    get_store_ratings_summary,
    get_product_ratings_summary,
)

from src.api.shared_schemas.product import ProductOut
from src.api.shared_schemas.rating import RatingsSummaryOut
from src.api.shared_schemas.store_theme import StoreThemeOut

from src.core import models
from src.core.database import get_db_manager

from src.api.app.schemas.order import Order
from src.api.app.services.authorize_totem import authorize_totem
from src.core.models import Coupon
from src.api.app.schemas.coupon import Coupon as CouponSchema
from src.socketio_instance import sio




# Evento de conexão do Socket.IO
@sio.event
async def connect(sid, environ):
    query = parse_qs(environ.get("QUERY_STRING", ""))
    token = query.get("totem_token", [None])[0]

    if not token:
        raise ConnectionRefusedError("Missing token")

    with get_db_manager() as db:
        totem = await authorize_totem(db, token)
        if not totem:
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
            joinedload(models.Store.cities).joinedload(models.StoreCity.neighborhoods),
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









def apply_coupon(coupon, price: float) -> float:
    if coupon.discount_percent:
        return round(price * (1 - coupon.discount_percent / 100), 2)
    elif coupon.discount_fixed:
        return max(0, price - coupon.discount_fixed)
    return price




@sio.event
async def send_order(sid, data):
    print('[SOCKET] Evento send_order recebido')
    print('[SOCKET] sid:', sid)
    print('[SOCKET] data:', data)

    with get_db_manager() as db:
        totem = db.query(models.TotemAuthorization).filter(models.TotemAuthorization.sid == sid).first()
        if not totem:
            return {'error': 'Totem não encontrado ou não autorizado'}

        try:
            new_order = NewOrder(**data)
        except ValidationError as e:
            return {'error': 'Dados do pedido inválidos', 'details': e.errors()}
        except Exception as e:
            return {'error': f'Erro inesperado: {str(e)}'}

        customer = db.query(models.Customer).filter_by(id=new_order.customer_id).first()
        if not customer:
            return {'error': 'Cliente não encontrado'}

        if not new_order.delivery_type:
            return {'error': 'Tipo de entrega é obrigatório'}

        optional_coupon = None
        if new_order.coupon_code:
            optional_coupon = db.query(Coupon).filter_by(code=new_order.coupon_code).first()

        try:
            db_order = models.Order(
                sequential_id=gerar_sequencial_do_dia(db, totem.store_id),
                public_id=generate_unique_public_id(db, totem.store_id),
                store_id=totem.store_id,
                totem_id=totem.id,
                customer_id=new_order.customer_id,
                customer_name=new_order.customer_name,
                customer_phone=new_order.customer_phone,
                payment_method_name=new_order.payment_method_name,
                order_type='cardapio_digital',
                delivery_type=new_order.delivery_type,
                total_price=new_order.total_price,
                payment_method_id=new_order.payment_method_id,
                payment_status='pendent',
                order_status='pendent',
                needs_change=new_order.needs_change,
                change_amount=new_order.change_for,
                observation=new_order.observation,
                delivery_fee=int(new_order.delivery_fee or 0),
                coupon_id=optional_coupon.id if optional_coupon else None,
                street=new_order.street,
                number=new_order.number,
                complement=new_order.complement,
                neighborhood=new_order.neighborhood,
                city=new_order.city,
            )

            products_from_db = db.query(models.Product).filter(
                models.Product.store_id == totem.store_id,
                models.Product.id.in_([p.product_id for p in new_order.products])
            ).all()
            products_map = {p.id: p for p in products_from_db}

            coupon_codes = [p.coupon_code for p in new_order.products if p.coupon_code]
            if new_order.coupon_code:
                coupon_codes.append(new_order.coupon_code)

            coupons = db.query(models.Coupon).filter(
                models.Coupon.store_id == totem.store_id,
                models.Coupon.code.in_(coupon_codes),
                models.Coupon.used < models.Coupon.max_uses,
                or_(models.Coupon.start_date == None, models.Coupon.start_date <= datetime.datetime.utcnow()),
                or_(models.Coupon.end_date == None, models.Coupon.end_date >= datetime.datetime.utcnow())
            ).all()
            coupon_map = {c.code: c for c in coupons}

            total_price_calculated_backend = 0

            for order_product_data in new_order.products:
                validate_order_variants(db, order_product_data)

                product_db = products_map.get(order_product_data.product_id)
                if not product_db:
                    return {'error': f"Produto com ID {order_product_data.product_id} não encontrado."}

                if order_product_data.coupon_code:
                    coupon = coupon_map.get(order_product_data.coupon_code)
                    if coupon and coupon.product_id == product_db.id:
                        price_with_coupon = apply_coupon(coupon, product_db.base_price)
                    else:
                        return {'error': f"Cupom inválido para o produto {product_db.name}"}
                else:
                    price_with_coupon = product_db.promotion_price or product_db.base_price

                if price_with_coupon != order_product_data.price:
                    return {'error': f"Preço inválido para {product_db.name}. Esperado: {price_with_coupon}, Recebido: {order_product_data.price}"}

                db_product_entry = models.OrderProduct(
                    store_id=totem.store_id,
                    product_id=product_db.id,
                    name=product_db.name,
                    price=int(price_with_coupon),
                    quantity=order_product_data.quantity,
                    note=order_product_data.note,
                )
                db_order.products.append(db_product_entry)

                current_product_total = price_with_coupon * order_product_data.quantity
                variants_price = 0

                variant_links = db.query(models.ProductVariantProduct).filter_by(product_id=product_db.id).all()
                variant_map = {link.variant_id: link.variant for link in variant_links}

                for order_variant_data in order_product_data.variants:
                    variant = variant_map.get(order_variant_data.variant_id)
                    if not variant:
                        return {'error': f"Variante inválida: {order_variant_data.variant_id}"}

                    db_variant = models.OrderVariant(
                        store_id=totem.store_id,
                        order_product=db_product_entry,
                        variant_id=variant.id,
                        name=variant.name,
                    )
                    db_product_entry.variants.append(db_variant)

                    valid_options = db.query(models.VariantOptions).filter_by(variant_id=variant.id).all()
                    option_map = {opt.id: opt for opt in valid_options}

                    for order_option_data in order_variant_data.options:
                        option = option_map.get(order_option_data.variant_option_id)
                        if not option:
                            return {'error': f"Opção inválida: {order_option_data.variant_option_id}"}

                        if option.price != order_option_data.price:
                            return {'error': f"Preço incorreto na opção {option.name} da variante {variant.name}"}

                        db_option = models.OrderVariantOption(
                            store_id=totem.store_id,
                            order_variant=db_variant,
                            variant_option_id=option.id,
                            name=option.name,
                            price=option.price,
                            quantity=order_option_data.quantity,
                        )
                        db_variant.options.append(db_option)
                        variants_price += db_option.price * db_option.quantity

                total_price_calculated_backend += current_product_total + variants_price

            # Aplica cupom geral (de pedido)
            order_coupon = None
            if new_order.coupon_code:
                potential_order_coupon = coupon_map.get(new_order.coupon_code)
                if potential_order_coupon and potential_order_coupon.product_id is None:
                    order_coupon = potential_order_coupon
                    discounted_total = apply_coupon(order_coupon, total_price_calculated_backend)
                else:
                    return {"error": "Cupom geral inválido para o pedido."}
            else:
                discounted_total = total_price_calculated_backend

            # Soma taxa de entrega
            if new_order.delivery_fee:
                discounted_total += new_order.delivery_fee

            # Validação final do total
            if new_order.total_price != discounted_total:
                return {"error": f"Total incorreto. Esperado: {discounted_total}, Recebido: {new_order.total_price}"}

            db_order.total_price = discounted_total
            db_order.coupon_id = order_coupon.id if order_coupon else None
            db_order.discounted_total_price = discounted_total



            if order_coupon:
                db_order.coupon_id = order_coupon.id

            for coupon in coupons:
                coupon.used += 1

            db.add(db_order)

            # Atualiza o vínculo do cliente com a loja
            register_customer_store_relationship(
                db=db,
                store_id=totem.store_id,
                customer_id=new_order.customer_id,
                order_total=discounted_total
            )

            db.commit()


            await asyncio.create_task(emit_order_updated(db_order, db_order.store_id))

            db.refresh(db_order)


            order_dict = Order.model_validate(db_order).model_dump()
            return {"success": True, "order": order_dict}

        except sqlalchemy.exc.IntegrityError as e:
            db.rollback()
            return {"error": "Erro ao salvar o pedido: integridade violada"}
        except Exception as e:
            db.rollback()
            return {"error": f"Erro interno ao processar o pedido: {str(e)}"}









@sio.event
def check_coupon(sid, data):
    with get_db_manager() as db:
        totem = db.query(models.TotemAuthorization).filter(models.TotemAuthorization.sid == sid).first()

        if not totem:
            raise Exception('Totem does not exist')

        coupon_orm = db.query(models.Coupon).filter(
            models.Coupon.code == data,
            models.Coupon.store_id == totem.store_id
        ).first()

        if not coupon_orm or coupon_orm.used >= coupon_orm.max_uses:
            return {'error': 'Cupom inválido'}

        now = datetime.datetime.now(datetime.timezone.utc)
        if coupon_orm.start_date and now < coupon_orm.start_date:
            return {'error': 'Cupom inválido'}
        elif coupon_orm.end_date and now > coupon_orm.end_date:
            return {'error': 'Cupom inválido'}

        # Aqui converte o ORM para schema Pydantic
        coupon_schema = CouponSchema.model_validate(coupon_orm)

        return jsonable_encoder(coupon_schema)


@sio.event
def list_coupons(sid):
    with get_db_manager() as db:
        totem = db.query(models.TotemAuthorization).filter(models.TotemAuthorization.sid == sid).first()

        if not totem:
            return {'error': 'Totem não autorizado'}

        now = datetime.datetime.utcnow()

        coupons_orm = db.query(models.Coupon).filter(
            models.Coupon.store_id == totem.store_id,
            models.Coupon.used < models.Coupon.max_uses,
            or_(models.Coupon.start_date == None, models.Coupon.start_date <= now),
            or_(models.Coupon.end_date == None, models.Coupon.end_date >= now),
        ).all()

        coupons_schema = [CouponSchema.model_validate(c).model_dump() for c in coupons_orm]

        return {
            'coupons': coupons_schema
        }