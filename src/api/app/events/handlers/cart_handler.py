# =====================================================================================
# HANDLER DE CARRINHO DE COMPRAS (VERSÃO PROFISSIONAL E DEFINITIVA)
# =====================================================================================

import traceback
from sqlalchemy.orm import selectinload, joinedload
from pydantic import ValidationError

from src.core import models
from src.core.database import get_db_manager
from src.socketio_instance import sio
from src.api.schemas.cart import (CartSchema, CartItemSchema, ProductSummarySchema,
                                  CartItemVariantSchema, CartItemVariantOptionSchema,
                                  UpdateCartItemInput)



def _get_item_fingerprint(product_id: int, variants_input: list[dict]) -> str:
    """
    Cria uma "impressão digital" única para um item e sua configuração de variantes.
    Isso garante que um "X-Burger com Bacon" seja diferente de um "X-Burger com Queijo".
    """
    if not variants_input:
        return f"prod:{product_id}"

    parts = []
    # Ordena para garantir que a ordem das variantes não mude o fingerprint
    for variant in sorted(variants_input, key=lambda v: v['variant_id']):
        variant_id = variant['variant_id']
        # Ordena as opções para garantir consistência
        option_ids = sorted([opt['variant_option_id'] for opt in variant['options']])
        parts.append(f"var{variant_id}-opts{','.join(map(str, option_ids))}")

    return f"prod:{product_id}|" + '|'.join(parts)


def _get_full_cart_query(db, customer_id: int, store_id: int) -> models.Cart | None:
    """Busca o carrinho ATIVO do cliente com todos os dados relacionados de forma otimizada."""
    # (Esta função permanece a mesma da versão anterior, é uma boa query)
    return db.query(models.Cart).options(
        selectinload(models.Cart.items).options(
            joinedload(models.CartItem.product),
            selectinload(models.CartItem.variants).options(
                selectinload(models.CartItemVariant.options).options(
                    joinedload(models.CartItemVariantOption.variant_option).options(
                        joinedload(models.VariantOption.linked_product)
                    )
                )
            )
        ),
        joinedload(models.Cart.coupon)
    ).filter(
        models.Cart.customer_id == customer_id,
        models.Cart.store_id == store_id,
        models.Cart.status == models.CartStatus.ACTIVE
    ).first()


def _build_cart_schema(db_cart: models.Cart) -> CartSchema:
    """Calcula totais e converte o objeto do banco para o Schema de resposta."""
    if not db_cart:
        return CartSchema(id=0, status='empty', items=[], subtotal=0, discount=0, total=0)

    # ... (Lógica de cálculo, agora usando o método get_price()) ...
    cart_items_schemas = []
    subtotal = 0
    for item in db_cart.items:
        variants_price = 0
        variants_schemas = []
        for variant in item.variants:
            options_schemas = []
            for option in variant.options:
                # ✅ USA O MÉTODO INTELIGENTE DO MODELO! MUITO MAIS LIMPO!
                variants_price += option.variant_option.get_price() * option.quantity
                options_schemas.append(CartItemVariantOptionSchema.model_validate(option))
            variants_schemas.append(CartItemVariantSchema(variant_id=variant.variant_id, options=options_schemas))

        base_price = item.product.promotion_price if item.product.activate_promotion else item.product.base_price
        unit_price = base_price + variants_price
        total_item_price = unit_price * item.quantity
        subtotal += total_item_price

        cart_items_schemas.append(CartItemSchema.from_orm(item,
                                                          {'unit_price': unit_price, 'total_price': total_item_price,
                                                           'product': ProductSummarySchema.from_orm(item.product),
                                                           'variants': variants_schemas}))

    discount = 0
    # ✅ USA A PROPRIEDADE INTELIGENTE DO MODELO!
    if db_cart.coupon and db_cart.coupon.is_valid:
        # Lógica de cálculo do desconto aqui
        pass

    total = subtotal - discount

    return CartSchema.from_orm(db_cart, {'items': cart_items_schemas, 'subtotal': subtotal, 'discount': discount,
                                         'total': total})


# =====================================================================================
# SEÇÃO 2: EVENTOS SOCKET.IO
# =====================================================================================

@sio.event
async def get_or_create_cart(sid, data=None):
    # (Este evento permanece o mesmo, pois sua lógica já era sólida)
    print(f'[CART] Evento get_or_create_cart recebido do SID: {sid}')
    with get_db_manager() as db:
        try:
            session = db.query(models.StoreSession).filter_by(sid=sid).first()
            if not session or not session.customer_id: return {'error': 'Usuário não autenticado'}
            cart = _get_full_cart_query(db, session.customer_id, session.store_id)
            if not cart:
                cart = models.Cart(customer_id=session.customer_id, store_id=session.store_id)
                db.add(cart)
                db.commit();
                db.refresh(cart)
            final_cart_schema = _build_cart_schema(cart)
            return {"success": True, "cart": final_cart_schema.model_dump(mode="json")}
        except Exception as e:
            print(f"❌ Erro em get_or_create_cart: {e}\n{traceback.format_exc()}");
            return {"error": "Erro interno."}


@sio.event
async def update_cart_item(sid, data):
    """
    Versão profissional que VALIDA as regras de negócio ANTES de salvar.
    Agora suporta edição direta pelo `cart_item_id` ou adição via fingerprint.
    """
    print(f'[CART] Evento update_cart_item recebido: {data}')
    with get_db_manager() as db:
        try:
            update_data = UpdateCartItemInput.model_validate(data)
            session = db.query(models.StoreSession).filter_by(sid=sid).first()
            if not session or not session.customer_id:
                return {'error': 'Usuário não autenticado'}

            # Carrega ou cria carrinho
            cart = _get_full_cart_query(db, session.customer_id, session.store_id)
            if not cart:
                cart = models.Cart(customer_id=session.customer_id, store_id=session.store_id)
                db.add(cart)
                db.flush()

            # ✅ 1. Validação profissional das regras de negócio
            product = db.query(models.Product).options(
                selectinload(models.Product.variant_links)
            ).filter_by(id=update_data.product_id).first()
            if not product:
                return {'error': 'Produto não encontrado.'}

            product_rules = {link.variant_id: link for link in product.variant_links}
            if update_data.variants:
                for variant_input in update_data.variants:
                    rule = product_rules.get(variant_input.variant_id)
                    if not rule or not rule.available:
                        return {'error': 'Grupo de opção inválido para este produto.'}
                    if len(variant_input.options) < rule.min_selected_options:
                        return {'error': f'Escolha no mínimo {rule.min_selected_options} opção(ões).'}
                    if len(variant_input.options) > rule.max_selected_options:
                        return {'error': f'Escolha no máximo {rule.max_selected_options} opção(ões).'}

            # ✅ 2. Lógica de Edição vs. Adição
            fingerprint = _get_item_fingerprint(update_data.product_id, data.get('variants', []))
            cart_item_id_to_edit = data.get('cart_item_id')

            existing_item = None
            if cart_item_id_to_edit:
                # Modo edição pelo ID
                existing_item = db.query(models.CartItem).filter_by(
                    id=cart_item_id_to_edit,
                    cart_id=cart.id
                ).first()
            else:
                # Modo adição via fingerprint
                existing_item = db.query(models.CartItem).filter_by(
                    cart_id=cart.id,
                    fingerprint=fingerprint
                ).first()

            # ✅ 3. Inserção/atualização/remoção
            if update_data.quantity <= 0:
                if existing_item:
                    db.delete(existing_item)
            elif existing_item:
                existing_item.quantity = update_data.quantity
                existing_item.note = update_data.note
            else:
                new_item = models.CartItem(
                    cart_id=cart.id,
                    store_id=session.store_id,
                    product_id=update_data.product_id,
                    quantity=update_data.quantity,
                    note=update_data.note,
                    fingerprint=fingerprint
                )
                if update_data.variants:
                    for variant_input in update_data.variants:
                        new_variant = models.CartItemVariant(
                            variant_id=variant_input.variant_id,
                            store_id=session.store_id
                        )
                        for option_input in variant_input.options:
                            new_variant.options.append(
                                models.CartItemVariantOption(
                                    variant_option_id=option_input.variant_option_id,
                                    quantity=option_input.quantity,
                                    store_id=session.store_id
                                )
                            )
                        new_item.variants.append(new_variant)
                db.add(new_item)

            db.commit()

            # ✅ 4. Retorna carrinho atualizado
            updated_cart = _get_full_cart_query(db, session.customer_id, session.store_id)
            final_cart_schema = _build_cart_schema(updated_cart)
            return {"success": True, "cart": final_cart_schema.model_dump(mode="json")}

        except ValidationError as e:
            return {'error': 'Dados de entrada inválidos', 'details': e.errors()}
        except Exception as e:
            db.rollback()
            print(f"❌ Erro em update_cart_item: {e}\n{traceback.format_exc()}")
            return {"error": "Erro interno ao atualizar item."}


@sio.event
async def clear_cart(sid, data=None):
    # (Este evento permanece o mesmo, sua lógica já era sólida)
    print(f'[CART] Evento clear_cart recebido do SID: {sid}')
    with get_db_manager() as db:
        try:
            session = db.query(models.StoreSession).filter_by(sid=sid).first()
            if not session or not session.customer_id: return {'error': 'Usuário não autenticado'}
            cart = _get_full_cart_query(db, session.customer_id, session.store_id)
            if cart:
                cart.items = []
                cart.coupon_id = None  # Também limpa o cupom
                cart.coupon_code = None
                db.commit()
            updated_cart = _get_full_cart_query(db, session.customer_id, session.store_id)
            final_cart_schema = _build_cart_schema(updated_cart)
            return {"success": True, "cart": final_cart_schema.model_dump(mode="json")}
        except Exception as e:
            db.rollback()
            print(f"❌ Erro em clear_cart: {e}\n{traceback.format_exc()}");
            return {"error": "Erro interno."}