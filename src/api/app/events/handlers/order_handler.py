
from typing import cast



from src.api.admin.events.handlers.order_handler import process_new_order_automations
from src.api.admin.socketio.emitters import admin_emit_order_updated_from_obj
from src.api.admin.utils.order_code import generate_unique_public_id, gerar_sequencial_do_dia


from src.core import models

from src.core.database import get_db_manager
from src.core.utils.enums import OrderStatus, SalesChannel, PaymentStatus

from src.socketio_instance import sio

from src.api.schemas.orders.order import Order as OrderSchema


import traceback
from .cart_handler import _get_full_cart_query

from src.api.schemas.orders.new_order import CreateOrderInput  # Seu novo schema de entrada
from ...utils.coupon_logic import apply_coupon



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
                order_type=SalesChannel.MENU,
                delivery_type=input_data.delivery_type,
                observation=input_data.observation,
                needs_change=input_data.needs_change,
                change_amount=input_data.change_for,
                delivery_fee = input_data.delivery_fee,
                payment_status=PaymentStatus.PENDING,
                order_status=OrderStatus.PENDING
            )

            if address:
                db_order.street = address.street
                db_order.number = address.number
                db_order.complement = address.reference
                db_order.neighborhood = address.neighborhood_name  # ✅ Correto: usa o campo de texto
                db_order.city = address.city_name  # ✅ Correto: usa o campo de texto
            # 5. MAPEIA OS ITENS DO CARRINHO PARA ITENS DE PEDIDO E CALCULA O SUBTOTAL
            subtotal = 0
            for cart_item in cart.items:
                # ✅ --- LÓGICA DE PREÇO CORRIGIDA (IGUAL A DO CARRINHO) --- ✅

                # 1. Encontra o link da categoria para saber o preço base correto
                link = next(
                    (l for l in cart_item.product.category_links if l.category_id == cart_item.category_id),
                    None
                )
                if not link:
                    # Isso não deve acontecer se os dados estiverem consistentes, mas é um fallback seguro
                    raise Exception(
                        f"Não foi possível encontrar o preço para o produto {cart_item.product_id} na categoria {cart_item.category_id}")

                base_price = link.promotional_price if link.is_on_promotion else link.price

                # 2. Usa a propriedade correta (.resolved_price) para as opções
                variants_price = sum(
                    opt.variant_option.resolved_price * opt.quantity for v in cart_item.variants for opt in v.options)

                # O preço final do item é o preço base (da categoria) + o preço dos complementos
                final_item_price = base_price + variants_price

                subtotal += final_item_price * cart_item.quantity

                # --- FIM DA CORREÇÃO DE LÓGICA DE PREÇO ---

                # Cria o OrderProduct a partir do CartItem
                order_product = models.OrderProduct(
                    store_id=customer_session.store_id,
                    product_id=cart_item.product_id,
                    category_id=cart_item.category_id,
                    name=cart_item.product.name,
                    price=final_item_price,  # Usa o preço final calculado
                    quantity=cart_item.quantity,
                    note=cart_item.note,
                    image_url=cart_item.product.image_path,
                    original_price=base_price,  # Salva o preço base sem os adicionais
                )

                # Mapeia as variantes e opções do carrinho para o pedido
                for cart_variant in cart_item.variants:
                    order_variant = models.OrderVariant(
                        store_id=customer_session.store_id,
                        variant_id=cart_variant.variant_id,
                        name=cart_variant.variant.name
                    )
                    for cart_option in cart_variant.options:
                        order_variant.options.append(models.OrderVariantOption(
                            store_id=customer_session.store_id,
                            variant_option_id=cart_option.variant_option_id,
                            name=cart_option.variant_option.resolved_name,
                            # ✅ 3. Usa a propriedade correta aqui também
                            price=cart_option.variant_option.resolved_price,
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

            db_order.total_price = subtotal + db_order.delivery_fee
            db_order.discounted_total_price = (subtotal - discount) + db_order.delivery_fee


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