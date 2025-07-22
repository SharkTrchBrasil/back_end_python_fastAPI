# Correto - Importe datetime corretamente
from datetime import datetime, timezone

from operator import or_
from urllib.parse import parse_qs


import sqlalchemy
from fastapi.encoders import jsonable_encoder
from pydantic import ValidationError
from sqlalchemy.orm import joinedload

from src.api.admin.socketio.emitters import admin_emit_order_updated_from_obj, emit_new_order_notification
from src.api.admin.utils.order_code import generate_unique_public_id, gerar_sequencial_do_dia
from src.api.app.events.socketio_emitters import refresh_product_list

from src.api.app.schemas.new_order import NewOrder
from src.api.shared_schemas.coupon import CouponOut
from src.api.shared_schemas.store_details import StoreDetails
from src.api.app.services.add_customer_store import register_customer_store_relationship
from src.api.app.services.check_variants import validate_order_variants

from src.api.app.services.rating import (
    get_store_ratings_summary,

)


from src.api.shared_schemas.rating import RatingsSummaryOut
from src.api.shared_schemas.store_theme import StoreThemeOut

from src.core import models
from src.core.aws import get_presigned_url
from src.core.database import get_db_manager

from src.api.app.services.authorize_totem import authorize_totem


from src.socketio_instance import sio

from src.api.shared_schemas.order import Order as OrderSchema, OrderStatus


# Evento de conexão do Socket.IO
@sio.event
async def connect(sid, environ):
    query = parse_qs(environ.get("QUERY_STRING", ""))
    token = query.get("totem_token", [None])[0]

    if not token:
        raise ConnectionRefusedError("Missing token")

    with get_db_manager() as db:
        try:
            totem = await authorize_totem(db, token)
            if not totem or not totem.store:
                raise ConnectionRefusedError("Invalid or unauthorized token")

            # Cria/atualiza a sessão
            session = db.query(models.StoreSession).filter_by(sid=sid).first()
            if not session:
                session = models.StoreSession(
                    sid=sid,
                    store_id=totem.store.id,
                    client_type='totem'
                )
                db.add(session)
            else:
                session.store_id = totem.store.id
                session.client_type = 'totem'
                session.updated_at = datetime.utcnow()



            db.commit()
            print(f"✅ Totem session criada/atualizada para sid {sid}")

            room_name = f"store_{totem.store_id}"
            await sio.enter_room(sid, room_name)

            # Carrega dados completos da loja
            store = db.query(models.Store).options(
                joinedload(models.Store.payment_methods),
                joinedload(models.Store.delivery_config),
                joinedload(models.Store.hours),
                joinedload(models.Store.cities).joinedload(models.StoreCity.neighborhoods),
            ).filter_by(id=totem.store_id).first()

            if not store:
                raise ConnectionRefusedError("Store not found")

            try:
                store_schema = StoreDetails.model_validate(store)
                store_schema.ratingsSummary = RatingsSummaryOut(
                    **get_store_ratings_summary(db, store_id=store.id)
                )
                await sio.emit("store_updated", store_schema.model_dump(), to=sid)

                # Envia tema
                theme = db.query(models.StoreTheme).filter_by(store_id=totem.store_id).first()
                if theme:
                    await sio.emit(
                        "theme_updated",
                        StoreThemeOut.model_validate(theme).model_dump(),
                        to=sid,
                    )

                # Envia produtos e banners
                await refresh_product_list(db, totem.store_id, sid)

                banners = db.query(models.Banner).filter_by(store_id=totem.store_id).all()
                if banners:
                    from src.api.shared_schemas.banner import BannerOut
                    banner_payload = [BannerOut.model_validate(b).model_dump() for b in banners]
                    await sio.emit("banners_updated", banner_payload, to=sid)

            except Exception as e:
                print(f"Erro ao enviar dados iniciais: {e}")
                raise ConnectionRefusedError(f"Erro interno: {str(e)}")

        except Exception as e:
            db.rollback()
            print(f"❌ Erro na conexão do totem: {str(e)}")
            raise ConnectionRefusedError(str(e))


# Evento de desconexão do Socket.IO
@sio.event
async def disconnect(sid, reason):
    print("Totem disconnected", sid, reason)

    with get_db_manager() as db:
        try:
            # Remove a sessão do totem
            session = db.query(models.StoreSession).filter_by(sid=sid, client_type='totem').first()
            if session:
                await sio.leave_room(sid, f"store_{session.store_id}")
                db.delete(session)
                db.commit()
                print(f"✅ Totem session removida para sid {sid}")

            # Limpeza adicional (opcional) - remove sid de qualquer totem que ainda o tenha
            totem = db.query(models.TotemAuthorization).filter_by(sid=sid).first()
            if totem:
                totem.sid = None
                db.commit()

        except Exception as e:
            db.rollback()
            print(f"❌ Erro na desconexão do totem: {str(e)}")





def apply_coupon(coupon, price: float) -> float:
    if coupon.discount_type == 'percentage':
        return round(price * (1 - coupon.discount_value / 100), 2)
    elif coupon.discount_type == 'fixed':
        return max(0, price - coupon.discount_value)
    return price


@sio.event
async def send_order(sid, data):
    print('[SOCKET] Evento send_order recebido')
    print('[SOCKET] sid:', sid)
    print('[SOCKET] data:', data)

    with get_db_manager() as db:
        try:
            # 1. Verifica a sessão ativa
            session = db.query(models.StoreSession).filter_by(sid=sid).first()
            if not session or not session.store_id:
                return {'error': 'Sessão não autorizada'}

            # 2. Validação dos dados do pedido
            try:
                new_order = NewOrder(**data)
            except ValidationError as e:
                return {'error': 'Dados do pedido inválidos', 'details': e.errors()}
            except Exception as e:
                return {'error': f'Erro inesperado: {str(e)}'}

            # 3. Verifica se o cliente existe
            customer = db.query(models.Customer).filter_by(id=new_order.customer_id).first()
            if not customer:
                return {'error': 'Cliente não encontrado'}

            if not new_order.delivery_type:
                return {'error': 'Tipo de entrega é obrigatório'}

            # 4. Busca cupom se aplicável
            optional_coupon = None
            if new_order.coupon_code:
                optional_coupon = db.query(models.Coupon).filter_by(
                    code=new_order.coupon_code,
                    store_id=session.store_id
                ).first()



            # 5. Cria o pedido com todos os novos campos
            db_order = models.Order(
                sequential_id=gerar_sequencial_do_dia(db, session.store_id),
                public_id=generate_unique_public_id(db, session.store_id),
                store_id=session.store_id,
                customer_id=new_order.customer_id,
                customer_name=new_order.customer_name,
                customer_phone=new_order.customer_phone,
                payment_method_name=new_order.payment_method_name,
                order_type='cardapio_digital',
                delivery_type=new_order.delivery_type,
                total_price=new_order.total_price,
                payment_method_id=new_order.payment_method_id,
                payment_status='pending',
                order_status=OrderStatus.PENDING,
                needs_change=new_order.needs_change,
                change_amount=new_order.change_for,
                observation=new_order.observation,
                delivery_fee=int(new_order.delivery_fee or 0),
                coupon_id=optional_coupon.id if optional_coupon else None,
                street=new_order.street,
                number=new_order.number,
                attendant_name=new_order.attendant_name or "",
                complement=new_order.complement or "",
                neighborhood=new_order.neighborhood,
                city=new_order.city,
                is_scheduled=new_order.is_scheduled,
                scheduled_for=new_order.scheduled_for if new_order.scheduled_for else None,
                consumption_type=new_order.consumption_type,
                # Novos campos de desconto
                discount_amount=0,  # Será calculado abaixo
                discount_percentage=None,  # Será calculado abaixo
                discount_type=None,  # Será definido abaixo
                discount_reason=None,  # Será definido abaixo
                discounted_total_price=new_order.total_price,  # Valor inicial
            )

            # 6. Configuração automática da loja
            store_settings = db.query(models.StoreSettings).filter_by(store_id=session.store_id).first()
            if store_settings and store_settings.auto_accept_orders:
                db_order.order_status = OrderStatus.PREPARING

            # 7. Validação de produtos
            products_from_db = db.query(models.Product).filter(
                models.Product.store_id == session.store_id,
                models.Product.id.in_([p.product_id for p in new_order.products])
            ).all()
            products_map = {p.id: p for p in products_from_db}

            # 8. Validação de cupons
            coupon_codes = [p.coupon_code for p in new_order.products if p.coupon_code]
            if new_order.coupon_code:
                coupon_codes.append(new_order.coupon_code)

            coupons = db.query(models.Coupon).filter(
                models.Coupon.store_id == session.store_id,
                models.Coupon.code.in_(coupon_codes),
                models.Coupon.used < models.Coupon.max_uses,
                or_(models.Coupon.start_date == None, models.Coupon.start_date <= datetime.utcnow()),
                or_(models.Coupon.end_date == None, models.Coupon.end_date >= datetime.utcnow())
            ).all()
            coupon_map = {c.code: c for c in coupons}

            total_price_calculated_backend = 0
            total_discount_amount = 0

            # 9. Processamento de produtos e variantes
            for order_product_data in new_order.products:
                validate_order_variants(db, order_product_data)

                product_db = products_map.get(order_product_data.product_id)
                if not product_db:
                    return {'error': f"Produto com ID {order_product_data.product_id} não encontrado."}

                # Define preços originais e com desconto
                original_price = product_db.promotion_price or product_db.base_price
                final_price = original_price
                product_discount = 0

                # Aplica cupom de produto se existir
                if order_product_data.coupon_code:
                    coupon = coupon_map.get(order_product_data.coupon_code)
                    if coupon and coupon.product_id == product_db.id:
                        final_price = apply_coupon(coupon, original_price)
                        product_discount = original_price - final_price
                        total_discount_amount += product_discount * order_product_data.quantity
                    else:
                        return {'error': f"Cupom inválido para o produto {product_db.name}"}

                if final_price != order_product_data.price:
                    return {
                        'error': f"Preço inválido para {product_db.name}. Esperado: {final_price}, Recebido: {order_product_data.price}"}

                print(dir(product_db))  # This will show all available attributes
                # Cria o produto do pedido com todos os campos
                db_product_entry = models.OrderProduct(
                    store_id=session.store_id,
                    product_id=product_db.id,
                    name=product_db.name,
                    price=int(final_price),
                    quantity=order_product_data.quantity,
                    note=order_product_data.note,
                    image_url=product_db.image_path,
                   # file_key=product_db.file_key,
                    original_price=int(original_price),
                    discount_amount=product_discount,
                    discount_percentage=(product_discount / original_price * 100) if original_price > 0 else 0,
                )
                db_order.products.append(db_product_entry)

                current_product_total = final_price * order_product_data.quantity
                variants_price = 0

                # Processa variantes
                variant_links = db.query(models.ProductVariantProduct).filter_by(product_id=product_db.id).all()
                variant_map = {link.variant_id: link.variant for link in variant_links}

                for order_variant_data in order_product_data.variants:
                    variant = variant_map.get(order_variant_data.variant_id)
                    if not variant:
                        return {'error': f"Variante inválida: {order_variant_data.variant_id}"}

                    db_variant = models.OrderVariant(
                        store_id=session.store_id,
                        order_product=db_product_entry,
                        variant_id=variant.id,
                        name=variant.name,
                    )
                    db_product_entry.variants.append(db_variant)

                    # Processa opções
                    valid_options = db.query(models.VariantOptions).filter_by(variant_id=variant.id).all()
                    option_map = {opt.id: opt for opt in valid_options}

                    for order_option_data in order_variant_data.options:
                        option = option_map.get(order_option_data.variant_option_id)
                        if not option:
                            return {'error': f"Opção inválida: {order_option_data.variant_option_id}"}

                        if option.price != order_option_data.price:
                            return {'error': f"Preço incorreto na opção {option.name} da variante {variant.name}"}

                        db_option = models.OrderVariantOption(
                            store_id=session.store_id,
                            order_variant=db_variant,
                            variant_option_id=option.id,
                            name=option.name,
                            price=option.price,
                            quantity=order_option_data.quantity,
                        )
                        db_variant.options.append(db_option)
                        variants_price += db_option.price * db_option.quantity

                total_price_calculated_backend += current_product_total + variants_price

            # 9.5 Calcular subtotal_price
            db_order.subtotal_price = int(total_price_calculated_backend)

            # 10. Aplica cupom geral (de pedido)
            order_coupon = None
            if new_order.coupon_code:
                potential_order_coupon = coupon_map.get(new_order.coupon_code)
                if potential_order_coupon and potential_order_coupon.product_id is None:
                    order_coupon = potential_order_coupon
                    discounted_total = apply_coupon(order_coupon, total_price_calculated_backend)
                    # Calcula desconto total do cupom
                    order_discount = total_price_calculated_backend - discounted_total
                    total_discount_amount += order_discount

                    # Atualiza campos de desconto do pedido
                    db_order.discount_amount = total_discount_amount
                    db_order.discount_percentage = (
                                order_discount / total_price_calculated_backend * 100) if total_price_calculated_backend > 0 else 0
                    db_order.discount_type = order_coupon.discount_type  # 'fixed' ou 'percentage'

                    db_order.discount_reason = f"Cupom {order_coupon.code}"
                    db_order.coupon_code = order_coupon.code
                else:
                    return {"error": "Cupom geral inválido para o pedido."}
            else:
                discounted_total = total_price_calculated_backend
                # Se não tem cupom mas tem descontos em produtos
                if total_discount_amount > 0:
                    db_order.discount_amount = total_discount_amount
                    db_order.discount_percentage = (
                                total_discount_amount / total_price_calculated_backend * 100) if total_price_calculated_backend > 0 else 0
                    db_order.discount_type = 'product_discount'
                    db_order.discount_reason = 'Desconto em produtos'

            # 11. Adiciona taxa de entrega e valida total
            if new_order.delivery_fee:
                discounted_total += new_order.delivery_fee

            expected_total = round(discounted_total, 2)

            if round(new_order.total_price) != round(expected_total):

                return {"error": f"Total incorreto. Esperado: {expected_total}, Recebido: {new_order.total_price}"}

            db_order.total_price = total_price_calculated_backend + (new_order.delivery_fee or 0)
            db_order.coupon_id = order_coupon.id if order_coupon else None
            db_order.discounted_total_price = discounted_total

            # 12. Atualiza uso de cupons
            if order_coupon:
                order_coupon.used += 1

            db.add(db_order)

            # 13. Atualiza relacionamento cliente-loja
            register_customer_store_relationship(
                db=db,
                store_id=session.store_id,
                customer_id=new_order.customer_id,
                order_total=discounted_total
            )

            db.commit()

            # 14. Notifica atualização
            await admin_emit_order_updated_from_obj(db_order)

            db.refresh(db_order)


            # ✨ CORREÇÃO E LUGAR PERFEITO PARA A NOTIFICAÇÃO ✨
            # Não precisamos do 'if', pois sempre queremos notificar um novo pedido.
            # Apenas usamos a variável correta ('db_order').
            await emit_new_order_notification(db, store_id=db_order.store_id, order_id=db_order.id)




            return {
                "success": True,
                "order": OrderSchema.model_validate(db_order).model_dump()
            }

        except sqlalchemy.exc.IntegrityError as e:
            db.rollback()
            print(f"❌ Erro de integridade ao criar pedido: {str(e)}")
            return {"error": "Erro ao salvar o pedido: integridade violada"}

        except Exception as e:
            db.rollback()
            print(f"❌ Erro inesperado ao criar pedido: {str(e)}")
            return {"error": "Erro interno ao processar pedido"}











# @sio.event
# async def send_order(sid, data):
#     print('[SOCKET] Evento send_order recebido')
#     print('[SOCKET] sid:', sid)
#     print('[SOCKET] data:', data)
#
#     with get_db_manager() as db:
#         totem = db.query(models.TotemAuthorization).filter(models.TotemAuthorization.sid == sid).first()
#         if not totem:
#             return {'error': 'Totem não encontrado ou não autorizado'}
#
#         try:
#             new_order = NewOrder(**data)
#         except ValidationError as e:
#             return {'error': 'Dados do pedido inválidos', 'details': e.errors()}
#         except Exception as e:
#             return {'error': f'Erro inesperado: {str(e)}'}
#
#         customer = db.query(models.Customer).filter_by(id=new_order.customer_id).first()
#         if not customer:
#             return {'error': 'Cliente não encontrado'}
#
#         if not new_order.delivery_type:
#             return {'error': 'Tipo de entrega é obrigatório'}
#
#         optional_coupon = None
#         if new_order.coupon_code:
#             optional_coupon = db.query(Coupon).filter_by(code=new_order.coupon_code).first()
#
#         try:
#             db_order = models.Order(
#                 sequential_id=gerar_sequencial_do_dia(db, totem.store_id),
#                 public_id=generate_unique_public_id(db, totem.store_id),
#                 store_id=totem.store_id,
#                 totem_id=totem.id,
#                 customer_id=new_order.customer_id,
#                 customer_name=new_order.customer_name,
#                 customer_phone=new_order.customer_phone,
#                 payment_method_name=new_order.payment_method_name,
#                 order_type='cardapio_digital',
#                 delivery_type=new_order.delivery_type,
#                 total_price=new_order.total_price,
#                 payment_method_id=new_order.payment_method_id,
#                 payment_status='pendent',
#                 order_status='pendent',
#                 needs_change=new_order.needs_change,
#                 change_amount=new_order.change_for,
#                 observation=new_order.observation,
#                 delivery_fee=int(new_order.delivery_fee or 0),
#                 coupon_id=optional_coupon.id if optional_coupon else None,
#                 street=new_order.street,
#                 number=new_order.number,
#                 attendant_name=new_order.attendant_name or "",
#                 complement = new_order.complement or "",
#                 neighborhood=new_order.neighborhood,
#                     city=new_order.city,
#                 )
#
#             store_settings = db.query(models.StoreSettings).filter_by(store_id=totem.store_id).first()
#             if store_settings and store_settings.auto_accept_orders:
#                 db_order.order_status = 'preparing'
#
#             products_from_db = db.query(models.Product).filter(
#                 models.Product.store_id == totem.store_id,
#                 models.Product.id.in_([p.product_id for p in new_order.products])
#             ).all()
#             products_map = {p.id: p for p in products_from_db}
#
#             coupon_codes = [p.coupon_code for p in new_order.products if p.coupon_code]
#             if new_order.coupon_code:
#                 coupon_codes.append(new_order.coupon_code)
#
#             coupons = db.query(models.Coupon).filter(
#                 models.Coupon.store_id == totem.store_id,
#                 models.Coupon.code.in_(coupon_codes),
#                 models.Coupon.used < models.Coupon.max_uses,
#                 or_(models.Coupon.start_date == None, models.Coupon.start_date <= datetime.datetime.utcnow()),
#                 or_(models.Coupon.end_date == None, models.Coupon.end_date >= datetime.datetime.utcnow())
#             ).all()
#             coupon_map = {c.code: c for c in coupons}
#
#             total_price_calculated_backend = 0
#
#             for order_product_data in new_order.products:
#                 validate_order_variants(db, order_product_data)
#
#                 product_db = products_map.get(order_product_data.product_id)
#                 if not product_db:
#                     return {'error': f"Produto com ID {order_product_data.product_id} não encontrado."}
#
#                 if order_product_data.coupon_code:
#                     coupon = coupon_map.get(order_product_data.coupon_code)
#                     if coupon and coupon.product_id == product_db.id:
#                         price_with_coupon = apply_coupon(coupon, product_db.base_price)
#                     else:
#                         return {'error': f"Cupom inválido para o produto {product_db.name}"}
#                 else:
#                     price_with_coupon = product_db.promotion_price or product_db.base_price
#
#                 if price_with_coupon != order_product_data.price:
#                     return {'error': f"Preço inválido para {product_db.name}. Esperado: {price_with_coupon}, Recebido: {order_product_data.price}"}
#
#                 db_product_entry = models.OrderProduct(
#                     store_id=totem.store_id,
#                     product_id=product_db.id,
#                     name=product_db.name,
#                     price=int(price_with_coupon),
#                     quantity=order_product_data.quantity,
#                     note=order_product_data.note,
#                 )
#                 db_order.products.append(db_product_entry)
#
#                 current_product_total = price_with_coupon * order_product_data.quantity
#                 variants_price = 0
#
#                 variant_links = db.query(models.ProductVariantProduct).filter_by(product_id=product_db.id).all()
#                 variant_map = {link.variant_id: link.variant for link in variant_links}
#
#                 for order_variant_data in order_product_data.variants:
#                     variant = variant_map.get(order_variant_data.variant_id)
#                     if not variant:
#                         return {'error': f"Variante inválida: {order_variant_data.variant_id}"}
#
#                     db_variant = models.OrderVariant(
#                         store_id=totem.store_id,
#                         order_product=db_product_entry,
#                         variant_id=variant.id,
#                         name=variant.name,
#                     )
#                     db_product_entry.variants.append(db_variant)
#
#                     valid_options = db.query(models.VariantOptions).filter_by(variant_id=variant.id).all()
#                     option_map = {opt.id: opt for opt in valid_options}
#
#                     for order_option_data in order_variant_data.options:
#                         option = option_map.get(order_option_data.variant_option_id)
#                         if not option:
#                             return {'error': f"Opção inválida: {order_option_data.variant_option_id}"}
#
#                         if option.price != order_option_data.price:
#                             return {'error': f"Preço incorreto na opção {option.name} da variante {variant.name}"}
#
#                         db_option = models.OrderVariantOption(
#                             store_id=totem.store_id,
#                             order_variant=db_variant,
#                             variant_option_id=option.id,
#                             name=option.name,
#                             price=option.price,
#                             quantity=order_option_data.quantity,
#                         )
#                         db_variant.options.append(db_option)
#                         variants_price += db_option.price * db_option.quantity
#
#                 total_price_calculated_backend += current_product_total + variants_price
#
#             # Aplica cupom geral (de pedido)
#             order_coupon = None
#             if new_order.coupon_code:
#                 potential_order_coupon = coupon_map.get(new_order.coupon_code)
#                 if potential_order_coupon and potential_order_coupon.product_id is None:
#                     order_coupon = potential_order_coupon
#                     discounted_total = apply_coupon(order_coupon, total_price_calculated_backend)
#                 else:
#                     return {"error": "Cupom geral inválido para o pedido."}
#             else:
#                 discounted_total = total_price_calculated_backend
#
#             # Soma taxa de entrega
#             if new_order.delivery_fee:
#                 discounted_total += new_order.delivery_fee
#
#             # Validação final do total
#             if new_order.total_price != discounted_total:
#                 return {"error": f"Total incorreto. Esperado: {discounted_total}, Recebido: {new_order.total_price}"}
#
#             db_order.total_price = discounted_total
#             db_order.coupon_id = order_coupon.id if order_coupon else None
#             db_order.discounted_total_price = discounted_total
#
#
#
#             if order_coupon:
#                 db_order.coupon_id = order_coupon.id
#
#             for coupon in coupons:
#                 coupon.used += 1
#
#             db.add(db_order)
#
#             # Atualiza o vínculo do cliente com a loja
#             register_customer_store_relationship(
#                 db=db,
#                 store_id=totem.store_id,
#                 customer_id=new_order.customer_id,
#                 order_total=discounted_total
#             )
#
#             db.commit()
#
#             await asyncio.create_task(admin_emit_order_updated_from_obj(db_order))
#
#             db.refresh(db_order)
#
#             order_dict = OrderSchema.model_validate(db_order).model_dump()
#
#             return {"success": True, "order": order_dict}
#
#         except sqlalchemy.exc.IntegrityError as e:
#             db.rollback()
#             return {"error": "Erro ao salvar o pedido: integridade violada"}
#
#         except Exception as e:
#             db.rollback()
#             return {"error": str(e)}


@sio.event
async def check_coupon(sid, data):
    with get_db_manager() as db:
        try:
            # 1. Verifica a sessão ativa
            session = db.query(models.StoreSession).filter_by(sid=sid).first()
            if not session or not session.store_id:
                return {'error': 'Sessão não autorizada'}

            # 2. Validação básica do input
            if not data or not isinstance(data, str):
                return {'error': 'Código do cupom inválido'}

            # 3. Busca o cupom vinculado à LOJA da sessão
            coupon = db.query(models.Coupon).filter(
                models.Coupon.code == data.strip(),
                models.Coupon.store_id == session.store_id
            ).first()

            # 4. Validações do cupom
            if not coupon:
                return {'error': 'Cupom não encontrado'}

            now = datetime.now(timezone.utc)

            if coupon.used >= coupon.max_uses:
                return {'error': 'Cupom já utilizado'}

            if coupon.start_date and now < coupon.start_date:
                return {'error': 'Cupom ainda não disponível'}

            if coupon.end_date and now > coupon.end_date:
                return {'error': 'Cupom expirado'}

            # 5. Retorna o cupom válido
            return jsonable_encoder(CouponOut.model_validate(coupon))

        except Exception as e:
            print(f"❌ Erro ao verificar cupom: {str(e)}")
            return {'error': 'Erro interno ao processar cupom'}


@sio.event
async def list_coupons(sid):
    with get_db_manager() as db:
        try:
            session = db.query(models.StoreSession).filter_by(sid=sid).first()
            if not session or not session.store_id:
                return {'error': 'Sessão não autorizada'}

            now = datetime.utcnow()

            coupons = db.query(models.Coupon).filter(
                models.Coupon.store_id == session.store_id,
                models.Coupon.used < models.Coupon.max_uses,
                or_(
                    models.Coupon.start_date == None,
                    models.Coupon.start_date <= now
                ),
                or_(
                    models.Coupon.end_date == None,
                    models.Coupon.end_date >= now
                )
            ).all()

            return {
                'coupons': [
                    CouponOut.model_validate(c).model_dump(mode="json")
                    for c in coupons
                ]
            }

        except Exception as e:
            print(f"❌ Erro ao listar cupons: {str(e)}")
            return {'error': 'Erro interno ao listar cupons'}
