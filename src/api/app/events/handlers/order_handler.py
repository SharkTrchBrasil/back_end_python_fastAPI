# Correto - Importe datetime corretamente
from datetime import datetime, timezone
from decimal import Decimal

from operator import or_
from typing import cast

import sqlalchemy

from pydantic import ValidationError
from sqlalchemy.orm import joinedload, selectinload

from src.api.admin.events.handlers.order_handler import process_new_order_automations
from src.api.admin.socketio.emitters import admin_emit_order_updated_from_obj, emit_new_order_notification
from src.api.admin.utils.order_code import generate_unique_public_id, gerar_sequencial_do_dia
from src.api.app.events.handlers.coupon_handler import apply_coupon_to_cart

from src.api.schemas.new_order import NewOrder



from src.api.app.services.add_customer_store import register_customer_store_relationship


from src.core import models

from src.core.database import get_db_manager




from src.socketio_instance import sio

from src.api.schemas.order import Order as OrderSchema


import traceback
from .cart_handler import _get_full_cart_query

from src.api.schemas.ordernew import CreateOrderInput  # Seu novo schema de entrada
from ...utils.coupon_logic import apply_coupon


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
                        final_price, _ = apply_coupon_to_cart(coupon, original_price)
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
                    discounted_total, order_discount = apply_coupon_to_cart(order_coupon, total_price_calculated_backend)
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


            final_order_for_automation = db.query(models.Order).options(
                selectinload(models.Order.products).options(
                    joinedload(models.OrderProduct.product).selectinload(models.Product.category)
                ),
                joinedload(models.Order.store).joinedload(models.Store.store_operation_config)
                # Também garante que as configs da loja estão carregadas
            ).filter(models.Order.id == db_order.id).one()

            # 14. Automações e Notificações
            # ✅ Passamos o objeto recarregado e completo para a função
            await process_new_order_automations(db, final_order_for_automation)

            # O restante das suas notificações pode usar o mesmo objeto
            await admin_emit_order_updated_from_obj(final_order_for_automation)
            await emit_new_order_notification(db, store_id=final_order_for_automation.store_id,
                                              order_id=final_order_for_automation.id)

            return {
                "success": True,
                "order": OrderSchema.model_validate(final_order_for_automation).model_dump()
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
async def create_order_from_cart(sid, data):
    """
    O novo evento para finalizar um pedido. Lê o carrinho do banco de dados,
    garantindo máxima segurança e consistência.
    """
    print(f'[ORDER] Evento create_order_from_cart recebido: {data}')
    with get_db_manager() as db:
        try:
            # 1. VALIDAÇÕES INICIAIS
            input_data = CreateOrderInput.model_validate(data)

            customer_session = db.query(models.CustomerSession).filter_by(sid=sid).first()
            if not customer_session or not customer_session.customer_id:
                return {'error': 'Usuário não autenticado na sessão.'}

            customer = db.query(models.Customer).filter_by(id=customer_session.customer_id).first()
            if not customer:
                return {'error': 'Cliente não encontrado'}

            # 2. ✅ BUSCA O CARRINHO DO BANCO DE DADOS (A FONTE DA VERDADE)
            cart = _get_full_cart_query(db, customer_session.customer_id, customer_session.store_id)
            if not cart or not cart.items:
                return {'error': 'Seu carrinho está vazio.'}

            # ✅ A CORREÇÃO FINAL ESTÁ AQUI
            payment_activation = db.query(models.StorePaymentMethodActivation).filter_by(
                platform_payment_method_id=input_data.payment_method_id,  # Procura pelo ID da plataforma
                store_id=customer_session.store_id,
                is_active=True
            ).first()

            if not payment_activation:
                # Agora esta mensagem só aparecerá se a forma de pagamento for realmente inválida
                return {'error': 'Forma de pagamento inválida ou inativa para esta loja.'}


            address = None
            if input_data.delivery_type == 'delivery':
                address = db.query(models.Address).filter_by(id=input_data.address_id,
                                                                     customer_id=customer_session.customer_id).first()
                if not address: return {'error': 'Endereço inválido.'}

            # 4. CRIA O OBJETO `Order` COM DADOS CONFIÁVEIS
            db_order = models.Order(
                sequential_id=gerar_sequencial_do_dia(db, customer_session.store_id),
                public_id=generate_unique_public_id(db, customer_session.store_id),
                store_id=customer_session.store_id,
                customer_id=customer.id,
                customer_name=customer.name,
                customer_phone=customer.phone,
                payment_method_id=payment_activation.id,
                payment_method_name=payment_activation.platform_method.name,
                order_type='cardapio_digital',
                delivery_type=input_data.delivery_type,
                observation=input_data.observation,
                needs_change=input_data.needs_change,
                change_amount=input_data.change_for,
                payment_status='pending',
                order_status='pending',
            )
            # Preenche o endereço se houver
            if address:
                db_order.street = address.street
                db_order.number = address.number
                db_order.complement = address.complement
                db_order.neighborhood = address.neighborhood
                db_order.city = address.city_name

            # 5. MAPEIA OS ITENS DO CARRINHO PARA ITENS DE PEDIDO E CALCULA O SUBTOTAL
            subtotal = 0
            for cart_item in cart.items:
                # Recalcula o preço final do item no servidor para 100% de segurança
                base_price = cart_item.product.promotion_price if cart_item.product.activate_promotion else cart_item.product.base_price
                variants_price = sum(opt.variant_option.get_price() for v in cart_item.variants for opt in v.options)
                final_item_price = base_price + variants_price

                subtotal += final_item_price * cart_item.quantity

                # Cria o OrderProduct a partir do CartItem
                order_product = models.OrderProduct(
                    store_id=customer_session.store_id, product_id=cart_item.product_id, name=cart_item.product.name,
                    price=final_item_price, quantity=cart_item.quantity, note=cart_item.note,
                    image_url=cart_item.product.image_path, original_price=base_price,
                )

                # Mapeia as variantes e opções do carrinho para o pedido
                for cart_variant in cart_item.variants:
                    order_variant = models.OrderVariant(store_id=customer_session.store_id, variant_id=cart_variant.variant_id,
                                                        name=cart_variant.variant.name)
                    for cart_option in cart_variant.options:
                        order_variant.options.append(models.OrderVariantOption(
                            store_id=customer_session.store_id, variant_option_id=cart_option.variant_option_id,
                            name=cart_option.variant_option.resolvedName, price=cart_option.variant_option.get_price(),
                            quantity=cart_option.quantity,
                        ))
                    order_product.variants.append(order_variant)
                db_order.products.append(order_product)

            db_order.subtotal_price = subtotal

            # 6. APLICA DESCONTOS E TOTAIS FINAIS (VERSÃO CORRIGIDA)
            discount = 0


            coupon = cast(models.Coupon, cart.coupon)
            if coupon and coupon.is_now_valid(subtotal_in_cents=subtotal, customer=customer):
                if coupon.product_id is None:  # Garante que é um cupom de carrinho
                    _, discount = apply_coupon(coupon, subtotal)
                    db_order.coupon = coupon

            db_order.discount_amount = discount

            delivery_fee = 0  # Adicione aqui sua lógica para calcular a taxa de entrega
            db_order.delivery_fee = delivery_fee

            db_order.total_price = subtotal + delivery_fee
            db_order.discounted_total_price = (subtotal - discount) + delivery_fee

            # 7. ATUALIZA O STATUS DO CARRINHO E DO CUPOM
            cart.status = models.CartStatus.COMPLETED
            if db_order.coupon:
                db_order.coupon.used += 1

            # 8. SALVA TUDO NO BANCO E DISPARA AUTOMAÇÕES
            db.add(db_order)
            db.commit()
            db.refresh(db_order)

            # Reutiliza suas funções de automação
            await process_new_order_automations(db, db_order)
            await admin_emit_order_updated_from_obj(db_order)

            return {"success": True, "order": OrderSchema.model_validate(db_order).model_dump()}

        except Exception as e:
            db.rollback()
            print(f"❌ Erro em create_order_from_cart: {e}\n{traceback.format_exc()}")
            return {"error": f"Erro interno ao criar pedido: {str(e)}"}