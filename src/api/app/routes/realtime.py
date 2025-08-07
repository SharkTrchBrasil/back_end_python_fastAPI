# Correto - Importe datetime corretamente
from datetime import datetime, timezone
from decimal import Decimal

from operator import or_
from urllib.parse import parse_qs


import sqlalchemy
from fastapi.encoders import jsonable_encoder
from pydantic import ValidationError
from sqlalchemy.orm import joinedload, selectinload

from src.api.admin.events.handlers.order_handler import process_new_order_automations
from src.api.admin.socketio.emitters import admin_emit_order_updated_from_obj, emit_new_order_notification
from src.api.admin.utils.order_code import generate_unique_public_id, gerar_sequencial_do_dia
from src.api.app.events.socketio_emitters import emit_products_updated, _prepare_products_payload

from src.api.app.schemas.new_order import NewOrder
from src.api.shared_schemas.banner import BannerOut
from src.api.shared_schemas.coupon import CouponOut
from src.api.shared_schemas.product import ProductOut
from src.api.shared_schemas.store_details import StoreDetails
from src.api.app.services.add_customer_store import register_customer_store_relationship
from src.api.app.services.check_variants import validate_order_variants

from src.api.app.services.rating import (
    get_store_ratings_summary, get_product_ratings_summary,
)

from src.api.shared_schemas.rating import RatingsSummaryOut
from src.api.shared_schemas.store_theme import StoreThemeOut

from src.core import models

from src.core.database import get_db_manager

from src.api.app.services.authorize_totem import authorize_totem


from src.socketio_instance import sio

from src.api.shared_schemas.order import Order as OrderSchema, OrderStatus


# Em seu arquivo de eventos do totem

@sio.event
async def connect(sid, environ):
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
                session = models.StoreSession(sid=sid, store_id=totem.store.id, client_type='totem')
                db.add(session)
            else:
                print("♻️ Atualizando sessão existente...")
                session.store_id = totem.store.id
                session.updated_at = datetime.utcnow()

            db.commit()
            print("💾 Sessão salva no banco")

            room_name = f"store_{totem.store_id}"
            print(f"🚪 Entrando na sala: {room_name}")
            await sio.enter_room(sid, room_name)
            print(f"✅ Cliente {sid} conectado e entrou na sala {room_name}")

            # SUPER CONSULTA
            print(f"🔍 Carregando estado completo para a loja {totem.store_id}...")

            store = db.query(models.Store).options(
                selectinload(models.Store.payment_activations)
                .selectinload(models.StorePaymentMethodActivation.platform_method)
                .selectinload(models.PlatformPaymentMethod.category)
                .selectinload(models.PaymentMethodCategory.group),

                joinedload(models.Store.store_operation_config),
                selectinload(models.Store.hours),
                selectinload(models.Store.cities).selectinload(models.StoreCity.neighborhoods),
                selectinload(models.Store.coupons),

                selectinload(models.Store.products)
                .selectinload(models.Product.variant_links)
                .selectinload(models.ProductVariantLink.variant)
                .selectinload(models.Variant.options)
                .selectinload(models.VariantOption.linked_product),

                selectinload(models.Store.variants).selectinload(models.Variant.options),
            ).filter(models.Store.id == totem.store_id).first()

            print(f"📦 Resultado da superconsulta: {'Encontrado' if store else 'NÃO encontrado'}")

            if not store:
                raise ConnectionRefusedError("Store not found after query")

            # Montagem do payload
            print("🧩 Validando loja com Pydantic...")
            store_schema = StoreDetails.model_validate(store)

            print("📊 Buscando resumo de avaliações...")
            store_schema.ratingsSummary = RatingsSummaryOut(**get_store_ratings_summary(db, store_id=store.id))

            print("🛠️ Preparando payload de produtos...")
            products_payload = _prepare_products_payload(db, store.products)

            print("🎨 Validando tema da loja...")
            theme = StoreThemeOut.model_validate(store.theme).model_dump(mode='json') if store.theme else None

            print("🖼️ Validando banners...")
            banners_payload = [BannerOut.model_validate(b).model_dump(mode='json') for b in store.banners] if store.banners else []

            initial_state_payload = {
                "store": store_schema.model_dump(mode='json'),
                "theme": theme,
                "products": products_payload,
                "banners": banners_payload
            }

            print("📡 Emitindo evento 'initial_state_loaded'...")
            await sio.emit("initial_state_loaded", initial_state_payload, to=sid)
            print(f"✅ Estado inicial completo enviado com sucesso para o cliente {sid}")

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

    with get_db_manager() as db:
        try:
            # 1. Validações Iniciais
            session = db.query(models.StoreSession).filter_by(sid=sid).first()
            if not session or not session.store_id:
                return {'error': 'Sessão não autorizada'}

            try:
                new_order = NewOrder(**data)
            except ValidationError as e:
                return {'error': 'Dados do pedido inválidos', 'details': e.errors()}

            customer = db.query(models.Customer).filter_by(id=new_order.customer_id).first()
            if not customer:
                return {'error': 'Cliente não encontrado'}

            if not new_order.delivery_type:
                return {'error': 'Tipo de entrega é obrigatório'}

            # 2. Validação do Método de Pagamento
            payment_activation = db.query(models.StorePaymentMethodActivation).options(
                joinedload(models.StorePaymentMethodActivation.platform_method)
            ).filter(
                models.StorePaymentMethodActivation.id == new_order.payment_method_id,
                models.StorePaymentMethodActivation.store_id == session.store_id,
                models.StorePaymentMethodActivation.is_active == True
            ).first()
            if not payment_activation:
                return {'error': 'Forma de pagamento inválida ou inativa.'}
            payment_method_name_from_db = payment_activation.platform_method.name

            # 4. Criação do Objeto do Pedido (sem valores financeiros)
            db_order = models.Order(
                sequential_id=gerar_sequencial_do_dia(db, session.store_id),
                public_id=generate_unique_public_id(db, session.store_id),
                store_id=session.store_id,
                customer_id=new_order.customer_id,
                customer_name=new_order.customer_name,
                customer_phone=new_order.customer_phone,
                payment_method_id=payment_activation.id,
                payment_method_name=payment_method_name_from_db,
                order_type='cardapio_digital',
                delivery_type=new_order.delivery_type,
                payment_status='pending',
                order_status='pending',
                needs_change=new_order.needs_change,
                change_amount=new_order.change_for,
                observation=new_order.observation,
                delivery_fee=int(new_order.delivery_fee or 0),
                street=new_order.street,
                number=new_order.number,
                attendant_name=new_order.attendant_name or "",
                complement=new_order.complement or "",
                neighborhood=new_order.neighborhood,
                city=new_order.city,
                is_scheduled=new_order.is_scheduled,
                scheduled_for=new_order.scheduled_for if new_order.scheduled_for else None,
                consumption_type=new_order.consumption_type,
            )

            # 5. Pré-carregamento de Cupons
            coupon_codes = [p.coupon_code for p in new_order.products if p.coupon_code]
            if new_order.coupon_code:
                coupon_codes.append(new_order.coupon_code)

            coupons_from_db = db.query(models.Coupon).filter(
                models.Coupon.store_id == session.store_id,
                models.Coupon.code.in_(coupon_codes),
                models.Coupon.used < models.Coupon.max_uses,
                or_(models.Coupon.start_date == None, models.Coupon.start_date <= datetime.utcnow()),
                or_(models.Coupon.end_date == None, models.Coupon.end_date >= datetime.utcnow())
            ).all()
            coupon_map = {c.code: c for c in coupons_from_db}

            # 6. Pré-carregamento e Validação "Fail-Fast" de Produtos e Opções
            product_ids = {p.product_id for p in new_order.products}
            option_ids = {opt.variant_option_id for p in new_order.products for v in p.variants for opt in v.options}

            products_from_db = db.query(models.Product).options(
                selectinload(models.Product.variant_links).selectinload(models.ProductVariantLink.variant)
            ).filter(models.Product.id.in_(product_ids), models.Product.store_id == session.store_id).all()
            products_map = {p.id: p for p in products_from_db}

            options_from_db = db.query(models.VariantOption).options(
                selectinload(models.VariantOption.linked_product)
            ).filter(models.VariantOption.id.in_(option_ids)).all()
            options_map = {opt.id: opt for opt in options_from_db}

            if len(products_map) != len(product_ids):
                return {'error': 'Um ou mais produtos no pedido são inválidos.'}
            if len(options_map) != len(option_ids):
                return {'error': 'Uma ou mais opções de complemento são inválidas.'}

            # 7. Loop de Processamento e Cálculo
            total_price_calculated_backend = 0
            total_discount_amount = 0

            # 9.3. Loop de Validação e Processamento (usando dados pré-carregados)
            for order_product_data in new_order.products:
                product_db = products_map.get(order_product_data.product_id)
                if not product_db:
                    raise Exception(f"Produto com ID {order_product_data.product_id} não encontrado.")

                original_price = product_db.promotion_price if product_db.activate_promotion else product_db.base_price
                final_price = original_price
                product_discount = 0

                # Aplica cupom de produto se existir
                if order_product_data.coupon_code:
                    coupon = coupon_map.get(order_product_data.coupon_code)
                    if coupon and coupon.product_id == product_db.id:
                        final_price, _ = apply_coupon(coupon, original_price)
                        product_discount = original_price - final_price
                        total_discount_amount += product_discount * order_product_data.quantity
                    else:
                        raise Exception(f"Cupom inválido para o produto {product_db.name}")

                if final_price != order_product_data.price:
                    raise Exception(
                        f"Preço inválido para {product_db.name}. Esperado: {final_price}, Recebido: {order_product_data.price}")

                db_product_entry = models.OrderProduct(
                    store_id=session.store_id,
                    product_id=product_db.id,
                    name=product_db.name,
                    price=int(final_price),
                    quantity=order_product_data.quantity,
                    note=order_product_data.note,
                    image_url=product_db.image_path,
                    original_price=int(original_price),
                    discount_amount=int(product_discount),
                )
                db_order.products.append(db_product_entry)

                current_product_total = final_price * order_product_data.quantity
                variants_price = 0

                product_rules_map = {link.variant_id: link for link in product_db.variant_links}

                for order_variant_data in order_product_data.variants:
                    rule = product_rules_map.get(order_variant_data.variant_id)
                    if not rule:
                        raise Exception(
                            f"O grupo de complemento ID {order_variant_data.variant_id} não é válido para este produto.")

                    num_selected_options = len(order_variant_data.options)
                    if num_selected_options < rule.min_selected_options:
                        raise Exception(
                            f"Para o grupo '{rule.variant.name}', o mínimo é {rule.min_selected_options} opções, mas {num_selected_options} foram enviadas.")
                    if num_selected_options > rule.max_selected_options:
                        raise Exception(
                            f"Para o grupo '{rule.variant.name}', o máximo é {rule.max_selected_options} opções, mas {num_selected_options} foram enviadas.")

                    if rule.max_total_quantity is not None:
                        total_quantity_in_group = sum(opt.quantity for opt in order_variant_data.options)
                        if total_quantity_in_group > rule.max_total_quantity:
                            raise Exception(
                                f"Para o grupo '{rule.variant.name}', a soma máxima das quantidades é {rule.max_total_quantity}, mas {total_quantity_in_group} foram enviadas.")

                    db_variant = models.OrderVariant(
                        store_id=session.store_id,
                        order_product=db_product_entry,
                        variant_id=rule.variant_id,
                        name=rule.variant.name,
                    )
                    db_product_entry.variants.append(db_variant)

                    for order_option_data in order_variant_data.options:
                        option_db = options_map.get(order_option_data.variant_option_id)
                        if not option_db or option_db.variant_id != order_variant_data.variant_id:
                            raise Exception(f"Opção inválida: {order_option_data.variant_option_id}")

                        backend_price = option_db.price_override if option_db.price_override is not None else (
                            option_db.linked_product.base_price if option_db.linked_product else 0)

                        if backend_price != order_option_data.price:
                            raise Exception(
                                f"Preço incorreto na opção. Esperado: {backend_price}, Recebido: {order_option_data.price}")

                        db_option = models.OrderVariantOption(
                            store_id=session.store_id,
                            order_variant=db_variant,
                            variant_option_id=option_db.id,
                            name=option_db.name_override or (
                                option_db.linked_product.name if option_db.linked_product else "N/A"),
                            price=backend_price,
                            quantity=order_option_data.quantity,
                        )
                        db_variant.options.append(db_option)
                        variants_price += db_option.price * db_option.quantity

                total_price_calculated_backend += current_product_total + variants_price

            #############################################################################
            # FIM DA SEÇÃO REFATORADA
            #############################################################################

            # 9.5 Calcular subtotal
            db_order.subtotal_price = int(total_price_calculated_backend)

            # 10. Aplica cupom geral (de pedido)
            order_coupon = None
            if new_order.coupon_code and new_order.coupon_code in coupon_map:
                potential_order_coupon = coupon_map[new_order.coupon_code]
                if potential_order_coupon.product_id is None:  # Garante que é um cupom de pedido
                    order_coupon = potential_order_coupon
                    discounted_total, order_discount = apply_coupon(order_coupon, total_price_calculated_backend)
                    total_discount_amount += order_discount
                    db_order.coupon_code = order_coupon.code
                    db_order.coupon_id = order_coupon.id
                else:
                    # Este caso pode ser tratado como erro ou simplesmente ignorado se o cupom já foi usado no produto
                    pass

            db_order.discount_amount = int(total_discount_amount)
            if total_price_calculated_backend > 0:
                db_order.discount_percentage = (total_discount_amount / total_price_calculated_backend) * 100


            # ##########################################################################
            # ✅ --- INÍCIO DA LÓGICA DE USO DE CASHBACK ---
            # ##########################################################################

            cashback_to_use_in_cents = new_order.apply_cashback_amount or 0

            if cashback_to_use_in_cents > 0:
                # 1. Valida se o cliente tem saldo suficiente.
                # A variável `customer` já foi buscada no início da função.
                if customer.cashback_balance < cashback_to_use_in_cents:
                    raise Exception("Saldo de cashback insuficiente.")

                # 2. Calcula o subtotal após descontos de cupons
                subtotal_after_coupons = total_price_calculated_backend - total_discount_amount

                # 3. Valida se o cashback não é maior que o valor a ser pago
                if cashback_to_use_in_cents > subtotal_after_coupons:
                    raise Exception("O valor de cashback utilizado não pode ser maior que o subtotal do pedido.")

                # 4. Adiciona o cashback ao montante total de descontos
                total_discount_amount += cashback_to_use_in_cents

                # 5. Registra o valor de cashback usado no pedido para auditoria
                db_order.cashback_used = cashback_to_use_in_cents

            # ##########################################################################
            # ✅ --- FIM DA LÓGICA DE USO DE CASHBACK ---
            # ##########################################################################

            final_total = total_price_calculated_backend - total_discount_amount + (new_order.delivery_fee or 0)



            # 11. Valida total final
            if abs(new_order.total_price - final_total) > 0.01:  # Comparação de floats com tolerância
                raise Exception(f"Total incorreto. Esperado: {final_total:.2f}, Recebido: {new_order.total_price:.2f}")

            # ✅ MELHORIA 3: Atribuição única e clara dos valores finais
            db_order.subtotal_price = int(total_price_calculated_backend)
            db_order.total_price = int(total_price_calculated_backend + db_order.delivery_fee)
            db_order.discounted_total_price = int(final_total)
            db_order.discount_amount = int(total_discount_amount)




            # 12. Atualiza uso de cupons
            for coupon in coupon_map.values():
                coupon.used += 1  # Ajuste essa lógica conforme necessário para contar usos

            db.add(db_order)

            # 13. Atualiza relacionamento cliente-loja
            register_customer_store_relationship(
                db=db,
                store_id=session.store_id,
                customer_id=new_order.customer_id,
                order_total=final_total
            )

            # ✅ --- DÉBITO DE CASHBACK E CRIAÇÃO DA TRANSAÇÃO ---
            if cashback_to_use_in_cents > 0:
                # Debita o saldo do objeto 'customer' que já está na sessão do DB
                customer.cashback_balance -= cashback_to_use_in_cents

                # Cria a transação de débito (valor negativo)
                debit_transaction = models.CashbackTransaction(
                    user_id=customer.id,
                    order=db_order,  # Associa a transação ao pedido
                    amount=-(Decimal(cashback_to_use_in_cents) / 100),
                    type="used",
                    description=f"Uso de cashback no pedido #{db_order.public_id}"
                )
                db.add(debit_transaction)

            db.commit()

            db.refresh(db_order)

            # 14. Automações e Notificações
            await process_new_order_automations(db, db_order)
            await admin_emit_order_updated_from_obj(db_order)
            await emit_new_order_notification(db, store_id=db_order.store_id, order_id=db_order.id)

            return {
                "success": True,
                "order": OrderSchema.model_validate(db_order).model_dump()
            }

        except sqlalchemy.exc.IntegrityError as e:
            db.rollback()
            print(f"❌ Erro de integridade ao criar pedido: {e}")
            return {"error": "Erro ao salvar o pedido: um dos identificadores pode estar duplicado ou inválido."}

        except Exception as e:
            db.rollback()
            print(f"❌ Erro inesperado ao criar pedido: {e.__class__.__name__}: {str(e)}")
            return {"error": f"Erro interno ao processar pedido: {str(e)}"}







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
