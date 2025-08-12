# =====================================================================================
# HANDLER DE CARRINHO DE COMPRAS (VERSÃO PROFISSIONAL E DEFINITIVA)
# =====================================================================================

import traceback
from sqlalchemy.orm import selectinload, joinedload
from pydantic import ValidationError

from src.api.app.utils.coupon_logic import apply_coupon
from src.core import models
from src.core.database import get_db_manager
from src.socketio_instance import sio
from src.api.schemas.cart import (CartSchema, CartItemSchema, ProductSummarySchema,
                                  CartItemVariantSchema, CartItemVariantOptionSchema,
                                  UpdateCartItemInput)



def _get_item_fingerprint(product_id: int, variants_input: list, note: str | None) -> str:
    """
    Cria uma "impressão digital" única para um item, agora incluindo a observação.
    """
    # Normaliza a nota: remove espaços extras e converte para minúsculas.
    # "Sem cebola" e " sem cebola " serão tratados como iguais.
    normalized_note = note.strip().lower() if note else ""

    if not variants_input and not normalized_note:
        return f"prod:{product_id}"

    parts = []
    if variants_input:
        for variant in sorted(variants_input, key=lambda v: v['variant_id']):
            variant_id = variant['variant_id']
            option_ids = sorted([opt['variant_option_id'] for opt in variant['options']])
            parts.append(f"var{variant_id}-opts{','.join(map(str, option_ids))}")

    # Adiciona a nota normalizada ao fingerprint se ela existir
    if normalized_note:
        parts.append(f"note:{normalized_note}")

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


# Em: app/events/handlers/cart_handler.py

def _build_cart_schema(db_cart: models.Cart) -> CartSchema:
    """
    Calcula totais e converte um objeto Cart do SQLAlchemy para um schema Pydantic,
    garantindo que todos os campos necessários para a UI (nomes, preços) sejam incluídos.
    """
    if not db_cart:
        return CartSchema(id=0, status='empty', items=[], subtotal=0, discount=0, total=0)

    cart_items_schemas = []
    subtotal = 0
    for item in db_cart.items:
        variants_price = 0
        variants_schemas = []
        for variant in item.variants:
            options_schemas = []
            for option in variant.options:
                db_option = option.variant_option

                # ✅ 1. PREENCHIMENTO EXPLÍCITO DOS DADOS DA OPÇÃO
                #    Em vez de `model_validate`, criamos o schema com todos os campos.
                option_price = db_option.get_price() * option.quantity
                variants_price += option_price

                options_schemas.append(CartItemVariantOptionSchema(
                    variant_option_id=option.variant_option_id,
                    quantity=option.quantity,
                    name=db_option.resolvedName,  # Usa a propriedade que criamos
                    price=db_option.get_price()  # Usa o método que criamos
                ))

            # ✅ 2. PREENCHIMENTO EXPLÍCITO DOS DADOS DA VARIANTE
            variants_schemas.append(CartItemVariantSchema(
                variant_id=variant.variant_id,
                name=variant.variant.name,  # Acessa o nome do grupo através da relação
                options=options_schemas
            ))

        base_price = item.product.promotion_price if item.product.activate_promotion else item.product.base_price
        unit_price = base_price + (variants_price // item.quantity if item.quantity > 0 else 0)
        total_item_price = unit_price * item.quantity
        subtotal += total_item_price

        # ✅ 3. CONSTRUÇÃO DO PRODUTO (JÁ ESTAVA QUASE CERTO)
        #    Garantimos que o ProductSummarySchema também seja criado corretamente.
        product_summary = ProductSummarySchema(
            id=item.product.id,
            name=item.product.name,
            image_url=item.product.image_path,
            description=item.product.description
        )

        cart_items_schemas.append(CartItemSchema(
            id=item.id,
            product=product_summary,
            quantity=item.quantity,
            note=item.note,
            variants=variants_schemas,
            unit_price=unit_price,
            total_price=total_item_price
        ))



    discount = 0
    if db_cart.coupon and db_cart.coupon.is_valid:
        # Importante: Apenas aplica o cupom se ele for para o carrinho inteiro
        # (sem um produto específico associado). Cupons de produto já são
        # calculados no seu `send_order`.
        if db_cart.coupon.product_id is None:
            # Chama a função de lógica com o subtotal que já calculamos.
            # O `_` ignora o novo preço, pois só precisamos do valor do desconto aqui.
            _, calculated_discount = apply_coupon(db_cart.coupon, subtotal)
            discount = calculated_discount

    # O total final é o subtotal menos o desconto calculado.
    total = subtotal - discount

    # Retorna o schema completo com os valores corretos.
    return CartSchema(
        id=db_cart.id,
        status=db_cart.status.value,
        coupon_code=db_cart.coupon_code,
        observation=db_cart.observation,
        items=cart_items_schemas,
        subtotal=subtotal,
        discount=discount,  # ✅ Preenchido
        total=total  # ✅ Preenchido
    )


# =====================================================================================
# SEÇÃO 2: EVENTOS SOCKET.IO
# =====================================================================================

# Em: app/events/handlers/cart_handler.py

@sio.event
async def get_or_create_cart(sid, data=None):
    """
    Busca o carrinho ativo de um cliente ou cria um novo.
    """
    print(f'[CART] Evento get_or_create_cart recebido do SID: {sid}')
    with get_db_manager() as db:
        try:
            # ✅ CORREÇÃO FINAL E DEFINITIVA:
            #    Busca diretamente na tabela 'CustomerSession', assim como as outras funções.
            customer_session = db.query(models.CustomerSession).filter_by(sid=sid).first()

            # A validação agora é mais simples e direta.
            if not customer_session or not customer_session.customer_id:
                return {'error': 'Usuário não autenticado na sessão.'}

            # Agora usamos os dados da customer_session para buscar o carrinho.
            cart = _get_full_cart_query(db, customer_session.customer_id, customer_session.store_id)

            if not cart:
                # E para criar o carrinho, se ele não existir.
                cart = models.Cart(
                    customer_id=customer_session.customer_id,
                    store_id=customer_session.store_id
                )
                db.add(cart)
                db.commit()
                db.refresh(cart)

            final_cart_schema = _build_cart_schema(cart)
            return {"success": True, "cart": final_cart_schema.model_dump(mode="json")}

        except Exception as e:
            print(f"❌ Erro em get_or_create_cart: {e}\n{traceback.format_exc()}")
            return {"error": "Erro interno."}



@sio.event
async def update_cart_item(sid, data):
    """
    Função definitiva para adicionar, atualizar, remover ou agrupar itens no carrinho,
    incluindo a manipulação completa de variantes e opções.
    """
    print(f'[CART] Evento update_cart_item recebido: {data}')
    with get_db_manager() as db:
        try:
            # 1. Validação do Payload e da Sessão
            update_data = UpdateCartItemInput.model_validate(data)
            customer_session = db.query(models.CustomerSession).filter_by(sid=sid).first()
            if not customer_session or not customer_session.customer_id:
                return {'error': 'Usuário não autenticado na sessão.'}

            # Carrega ou cria o carrinho
            cart = _get_full_cart_query(db, customer_session.customer_id, customer_session.store_id)
            if not cart:
                cart = models.Cart(customer_id=customer_session.customer_id, store_id=customer_session.store_id)
                db.add(cart);
                db.flush()

            # 2. Validação das Regras de Negócio (Segurança)
            product = db.query(models.Product).options(selectinload(models.Product.variant_links)).filter_by(
                id=update_data.product_id).first()
            if not product:
                return {'error': 'Produto não encontrado.'}

            product_rules = {link.variant_id: link for link in product.variant_links}
            if update_data.variants:
                for variant_input in update_data.variants:
                    rule = product_rules.get(variant_input.variant_id)
                    if not rule or not rule.available: return {'error': 'Grupo de opção inválido.'}
                    if len(variant_input.options) < rule.min_selected_options: return {
                        'error': f'Escolha no mínimo {rule.min_selected_options} opção(ões).'}
                    if len(variant_input.options) > rule.max_selected_options: return {
                        'error': f'Escolha no máximo {rule.max_selected_options} opção(ões).'}

            # --- LÓGICA PRINCIPAL: ADIÇÃO VS. EDIÇÃO ---

            cart_item_id_to_edit = update_data.cart_item_id

            if cart_item_id_to_edit:
                # --- MODO EDIÇÃO ---
                print(f"📝 Modo Edição para o item ID: {cart_item_id_to_edit}")
                existing_item = db.query(models.CartItem).filter_by(id=cart_item_id_to_edit, cart_id=cart.id).first()
                if not existing_item:
                    return {'error': 'Item para editar não encontrado.'}

                if update_data.quantity <= 0:
                    db.delete(existing_item)
                else:
                    # Atualiza os dados principais do item
                    existing_item.quantity = update_data.quantity
                    existing_item.note = update_data.note

                    # A forma mais segura de atualizar as variantes é "substituição total":
                    # 1. Deleta todas as variantes e opções antigas associadas a este item.
                    #    A configuração `cascade="all, delete-orphan"` no modelo cuida disso.
                    existing_item.variants = []
                    db.flush()  # Aplica a remoção no banco antes de adicionar as novas

                    # 2. Recria as variantes e opções com os novos dados do payload.
                    if update_data.variants:
                        for variant_input in update_data.variants:
                            new_variant = models.CartItemVariant(variant_id=variant_input.variant_id,
                                                                 store_id=customer_session.store_id)
                            for option_input in variant_input.options:
                                new_variant.options.append(models.CartItemVariantOption(
                                    variant_option_id=option_input.variant_option_id,
                                    quantity=option_input.quantity, store_id=customer_session.store_id
                                ))
                            existing_item.variants.append(new_variant)

                    # 3. Recalcula o fingerprint
                    existing_item.fingerprint = _get_item_fingerprint(
                        update_data.product_id, data.get('variants', []), update_data.note
                    )
            else:
                # --- MODO ADIÇÃO ---
                fingerprint = _get_item_fingerprint(
                    update_data.product_id, data.get('variants', []), update_data.note
                )
                existing_item = db.query(models.CartItem).filter_by(cart_id=cart.id, fingerprint=fingerprint).first()

                if existing_item:
                    # Se um item idêntico já existe, apenas soma a quantidade.
                    print(f"🔄 Item idêntico encontrado (ID: {existing_item.id}). Somando quantidade.")
                    existing_item.quantity += update_data.quantity
                else:
                    # Se não existe, cria um novo item.
                    print(f"✨ Item novo (Fingerprint: {fingerprint}). Criando no carrinho.")
                    new_item = models.CartItem(
                        cart_id=cart.id, store_id=customer_session.store_id,
                        product_id=update_data.product_id, quantity=update_data.quantity,
                        note=update_data.note, fingerprint=fingerprint
                    )
                    if update_data.variants:
                        for variant_input in update_data.variants:
                            new_variant = models.CartItemVariant(variant_id=variant_input.variant_id,
                                                                 store_id=customer_session.store_id)
                            for option_input in variant_input.options:
                                new_variant.options.append(models.CartItemVariantOption(
                                    variant_option_id=option_input.variant_option_id,
                                    quantity=option_input.quantity, store_id=customer_session.store_id
                                ))
                            new_item.variants.append(new_variant)
                    db.add(new_item)

            db.commit()

            # Retorna o estado atualizado e completo do carrinho
            updated_cart = _get_full_cart_query(db, customer_session.customer_id, customer_session.store_id)
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
            # ✅ CORREÇÃO: Busca na tabela correta 'CustomerSession'
            session = db.query(models.CustomerSession).filter_by(sid=sid).first()
            if not session or not session.customer_id:
                return {'error': 'Usuário não autenticado na sessão.'}

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
            print(f"❌ Erro em clear_cart: {e}\n{traceback.format_exc()}")
            return {"error": "Erro interno."}