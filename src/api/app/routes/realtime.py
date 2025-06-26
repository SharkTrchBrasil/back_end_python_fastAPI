import datetime
from operator import or_
from urllib.parse import parse_qs


import sqlalchemy
from fastapi.encoders import jsonable_encoder
from pydantic import ValidationError
from sqlalchemy.orm import joinedload

from src.api.admin.services.order_code import generate_unique_public_id, gerar_sequencial_do_dia

from src.api.app.schemas.new_order import NewOrder
from src.api.app.schemas.store_details import StoreDetails

from src.api.app.services.rating import (
    get_store_ratings_summary,
    get_product_ratings_summary,
)
from src.api.app.schemas.coupon import Coupon
from src.api.shared_schemas.product import ProductOut
from src.api.shared_schemas.rating import RatingsSummaryOut
from src.api.shared_schemas.store_theme import StoreThemeOut

from src.core import models
from src.core.database import get_db_manager

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
async def send_order(sid, data):
    print('[SOCKET] Evento send_order recebido')
    print('[SOCKET] sid:', sid)
    print('[SOCKET] data:', data)

    with get_db_manager() as db:
        totem = db.query(models.TotemAuthorization).filter(models.TotemAuthorization.sid == sid).first()
        if not totem:
            print(f"[SOCKET] Erro: Totem não encontrado ou não autorizado para sid: {sid}")
            return {'error': 'Totem não encontrado ou não autorizado'}

        try:
            # Tenta validar os dados de entrada usando o modelo Pydantic NewOrder
            new_order = NewOrder(**data)
        except ValidationError as e:
            print(f"[SOCKET] Erro de validação do pedido: {e.errors()}")
            serializable_errors = []
            for error_detail in e.errors():
                temp_error = error_detail.copy()
                # Verifica se há um 'ctx' e 'error' dentro dele
                if 'ctx' in temp_error and isinstance(temp_error['ctx'], dict) and 'error' in temp_error['ctx']:
                    # Se o 'error' for uma instância de ValueError, converte para string
                    if isinstance(temp_error['ctx']['error'], ValueError):
                        temp_error['ctx']['error'] = str(temp_error['ctx']['error'])
                serializable_errors.append(temp_error)
            return {'error': 'Dados do pedido inválidos', 'details': serializable_errors}
        except Exception as e:
            # Captura outros erros inesperados durante a validação inicial do Pydantic
            print(f"[SOCKET] Erro inesperado na validação inicial do Pydantic: {e}")
            return {"success": False, "error": f"Erro inesperado na validação dos dados: {str(e)}"}


        customer = db.query(models.Customer).filter_by(id=new_order.customer_id).first()
        if not customer:
            print(f"[SOCKET] Erro: Cliente com ID {new_order.customer_id} não encontrado.")
            return {'error': 'Cliente não encontrado'}

        address_id_to_use = None

        if new_order.address and new_order.address.id:
            address_id_to_use = new_order.address.id
        elif new_order.delivery_type == 'delivery' and new_order.address:

            print("[SOCKET] Aviso: Pedido de entrega com novo endereço sem ID. Considere salvar/associar o endereço antes.")



        try:
            db_order = models.Order(
                sequential_id=gerar_sequencial_do_dia(db, totem.store_id),
                public_id=generate_unique_public_id(db, totem.store_id),
                store_id=totem.store_id,
                totem_id=totem.id,
                customer_id=new_order.customer_id,
                customer_address_id=address_id_to_use, # Usando o ID do endereço, se disponível
                order_type='cardapio_digital', # Assumindo que este é o tipo fixo para pedidos de totem
                delivery_type=new_order.delivery_type,
                #total_price=new_order.total_price, # Agora o total_price vem do new_order validado
                payment_method_id=new_order.payment_method_id,
                payment_status='pendent', # Status inicial
                order_status='pendent',   # Status inicial
                needs_change=new_order.needs_change,
                change_amount=new_order.change_for, # Usando change_for para change_amount
                observation=new_order.observation,
                delivery_fee=new_order.delivery_fee,
            )

            # Após buscar os produtos do pedido:
            products_from_db = db.query(models.Product).filter(
                models.Product.store_id == totem.store_id,
                models.Product.id.in_([p.product_id for p in new_order.products])
            ).all()

            products_map = {p.id: p for p in products_from_db}

            # Buscar cupons
            coupon_codes = [p.coupon_code for p in new_order.products if p.coupon_code]
            if new_order.coupon_code:
                coupon_codes.append(new_order.coupon_code)

            coupons = db.query(models.Coupon).filter(
                models.Coupon.store_id == totem.store_id,
                models.Coupon.code.in_(coupon_codes),
                models.Coupon.used < models.Coupon.max_uses,
                or_(models.Coupon.start_date == None, models.Coupon.start_date <= datetime.datetime.utcnow()
),
                or_(models.Coupon.end_date == None, models.Coupon.end_date >= datetime.datetime.utcnow()
)
            ).all()

            # Mapeia cupons por código
            coupon_map = {c.code: c for c in coupons}

            # ... prossegue com products_map, variants_map, options_map ...
            total_price_calculated_backend = 0

            for order_product_data in new_order.products:
                product_db = products_map.get(order_product_data.product_id)
                if not product_db:
                    return {'error': f"Produto com ID {order_product_data.product_id} não encontrado."}

                # Aplica cupom se existir para este produto
                applied_coupon = None
                if order_product_data.coupon_code:
                    coupon = coupon_map.get(order_product_data.coupon_code)
                    if coupon and coupon.product_id == product_db.id:
                        applied_coupon = coupon
                        price_with_coupon = coupon.apply(product_db.base_price)
                    else:
                        return {'error': f"Cupom inválido para o produto {product_db.name}"}
                else:
                    price_with_coupon = product_db.base_price

                if price_with_coupon != order_product_data.price:
                    return {
                        'error': f"Preço inválido para o produto {product_db.name}. Esperado: {price_with_coupon}, Recebido: {order_product_data.price}"}

                db_product_entry = models.OrderProduct(
                    store_id=totem.store_id,
                    product_id=product_db.id,
                    name=product_db.name,
                    price=price_with_coupon,
                    quantity=order_product_data.quantity,
                    note=order_product_data.note,
                    coupon_id=applied_coupon.id if applied_coupon else None
                )
                db_order.products.append(db_product_entry)

                current_product_total = price_with_coupon * order_product_data.quantity

                # Varre variantes e opções normalmente...
                # (mantido seu código anterior para variantes e opções)

                total_price_calculated_backend += current_product_total

            # Aplica cupom de pedido geral (se houver e for válido)
            order_coupon = None
            if new_order.coupon_code:
                potential_order_coupon = coupon_map.get(new_order.coupon_code)
                if potential_order_coupon and potential_order_coupon.product_id is None:
                    order_coupon = potential_order_coupon
                    discounted_total = order_coupon.apply(total_price_calculated_backend)
                else:
                    return {"error": "Cupom geral inválido para o pedido."}
            else:
                discounted_total = total_price_calculated_backend

            # Soma taxa de entrega se tiver
            if new_order.delivery_fee:
                discounted_total += new_order.delivery_fee

            # Valida o total
            if new_order.total_price != discounted_total:
                return {"error": f"Total incorreto. Esperado: {discounted_total}, Recebido: {new_order.total_price}"}

            # Atribui total e cupom no pedido
            db_order.total_price = discounted_total
            if order_coupon:
                db_order.coupon_id = order_coupon.id
                db_order.discounted_total_price = discounted_total

            db.add(db_order)
            db.commit()

            # Após o commit, garanta que os produtos e variantes do pedido estão carregados para a serialização
            db.refresh(db_order)

            # Valida e converte o objeto de pedido do DB para o formato de saída (Order schema)
            order_dict = Order.model_validate(db_order).model_dump()
            print('[SOCKET] Pedido processado com sucesso e retornado ao cliente')
            return {"success": True, "order": order_dict}

        except sqlalchemy.exc.IntegrityError as e:
            db.rollback()
            print(f"[SOCKET] Erro de integridade ao processar o pedido (possível dado duplicado ou ausente): {e}")
            return {"success": False, "error": "Erro ao salvar o pedido devido a dados inválidos ou duplicados. Tente novamente."}
        except Exception as e:
            db.rollback()
            print(f"[SOCKET] Erro inesperado ao processar o pedido: {e}")
            return {"success": False, "error": f"Erro interno ao processar o pedido: {str(e)}"}

@sio.event
def check_coupon(sid, data):
    with(get_db_manager() as db):
        totem = db.query(models.TotemAuthorization).filter(models.TotemAuthorization.sid == sid).first()

        if not totem:
            raise Exception('Totem does not exist')

        coupon = db.query(models.Coupon).filter(
            models.Coupon.code == data,
            models.Coupon.store_id == totem.store_id
        ).first()

        if not coupon or coupon.used >= coupon.max_uses:
            return {'error': 'Cupom inválido'}

        now = datetime.datetime.now(datetime.timezone.utc)
        if coupon.start_date and now < coupon.start_date:
            return {'error': 'Cupom inválido'}
        elif coupon.end_date and now > coupon.end_date:
            return {'error': 'Cupom inválido'}


        return jsonable_encoder(Coupon.model_validate(coupon))

@sio.event
def list_coupons(sid):
    with get_db_manager() as db:
        totem = db.query(models.TotemAuthorization).filter(models.TotemAuthorization.sid == sid).first()

        if not totem:
            return {'error': 'Totem não autorizado'}

        now = datetime.datetime.utcnow()

        coupons = db.query(models.Coupon).filter(
            models.Coupon.store_id == totem.store_id,
            models.Coupon.used < models.Coupon.max_uses,
            or_(models.Coupon.start_date == None, models.Coupon.start_date <= now),
            or_(models.Coupon.end_date == None, models.Coupon.end_date >= now),
        ).all()

        return {
            'coupons': [Coupon.model_validate(c).model_dump() for c in coupons]
        }
