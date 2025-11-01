# =====================================================================================
# HANDLER DE CARRINHO DE COMPRAS (VERSÃO PROFISSIONAL E DEFINITIVA)
# =====================================================================================

import traceback
from sqlalchemy.orm import selectinload, joinedload
from pydantic import ValidationError

from src.api.app.utils.coupon_logic import apply_coupon
from src.api.schemas.products.product import ProductOut
from src.core import models
from src.core.database import get_db_manager
from src.socketio_instance import sio
from src.api.schemas.orders.cart import (CartSchema, CartItemSchema,
                                         CartItemVariantSchema, CartItemVariantOptionSchema,
                                         UpdateCartItemInput)



def _get_item_fingerprint(product_id: int, category_id: int, variants_input: list, note: str | None) -> str:
    """
    Cria uma "impressão digital" única para um item, incluindo produto, categoria, variantes e observação.
    
    Args:
        product_id: ID do produto
        category_id: ID da categoria
        variants_input: Lista de variantes (dicts ou objetos)
        note: Observação do item (pode ser None ou string vazia)
    
    Returns:
        String única que identifica a configuração completa do item
    """
    # ✅ CORREÇÃO: Garante que note é tratado corretamente (None ou string)
    if note is None:
        normalized_note = ""
    else:
        # Normaliza a nota: remove espaços extras e converte para minúsculas.
        # "Sem cebola" e " sem cebola " serão tratados como iguais.
        normalized_note = note.strip().lower() if note else ""

    parts = [f"prod:{product_id}", f"cat:{category_id}"]
    
    if variants_input:
        for variant in sorted(variants_input, key=lambda v: v.get('variant_id', 0) if isinstance(v, dict) else getattr(v, 'variant_id', 0)):
            if isinstance(variant, dict):
                variant_id = variant.get('variant_id', 0)
                options = variant.get('options', [])
            else:
                variant_id = getattr(variant, 'variant_id', 0)
                options = getattr(variant, 'options', [])
            
            if options:
                option_ids = []
                for opt in options:
                    if isinstance(opt, dict):
                        option_ids.append(opt.get('variant_option_id', 0))
                    else:
                        option_ids.append(getattr(opt, 'variant_option_id', 0))
                
                if option_ids:
                    sorted_option_ids = sorted([oid for oid in option_ids if oid > 0])
                    if sorted_option_ids:
                        parts.append(f"var{variant_id}-opts{','.join(map(str, sorted_option_ids))}")

    # Adiciona a nota normalizada ao fingerprint se ela existir
    if normalized_note:
        parts.append(f"note:{normalized_note}")

    return '|'.join(parts)


def _get_full_cart_query(db, customer_id: int, store_id: int) -> models.Cart | None:
    """Busca o carrinho ATIVO do cliente com todos os dados relacionados de forma otimizada."""
    # (Esta função permanece a mesma da versão anterior, é uma boa query)
    return db.query(models.Cart).options(
        selectinload(models.Cart.items).options(
            joinedload(models.CartItem.product).selectinload(models.Product.category_links),
            joinedload(models.CartItem.category),
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
    seguindo a nova arquitetura de preços por categoria.
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

                # 🔄 ATUALIZAÇÃO: Usa a propriedade 'resolved_price' que criamos no modelo,
                # que já contém a lógica de fallback correta.
                option_price = db_option.resolved_price * option.quantity
                variants_price += option_price

                options_schemas.append(CartItemVariantOptionSchema(
                    variant_option_id=option.variant_option_id,
                    quantity=option.quantity,
                    name=db_option.resolved_name,
                    price=db_option.resolved_price
                ))

            variants_schemas.append(CartItemVariantSchema(
                variant_id=variant.variant_id,
                name=variant.variant.name,
                options=options_schemas
            ))

        # ✅ --- LÓGICA DE PREÇO DO PRODUTO PRINCIPAL CORRIGIDA --- ✅
        # 1. Encontra o link específico para a categoria de onde este item foi adicionado.
        link = next(
            (l for l in item.product.category_links if l.category_id == item.category_id),
            None
        )

        # 2. Se não encontrar o link (improvável), usa 0. Senão, usa o preço correto.
        if not link:
            base_price = 0  # Fallback de segurança
        else:
            # Usa o preço promocional se a promoção estiver ativa, senão usa o preço normal do link.
            base_price = link.promotional_price if link.is_on_promotion else link.price
        # ✅ --- FIM DA CORREÇÃO --- ✅

        unit_price = base_price + (variants_price // item.quantity if item.quantity > 0 else 0)
        total_item_price = unit_price * item.quantity
        subtotal += total_item_price

        # A validação do ProductOut agora funciona, pois ele tem os campos calculados
        full_product_schema = ProductOut.model_validate(item.product)

        cart_items_schemas.append(CartItemSchema(
            id=item.id,
            product=full_product_schema,
            quantity=item.quantity,
            note=item.note,
            variants=variants_schemas,
            unit_price=unit_price,
            total_price=total_item_price
        ))

    # O resto da lógica de cupom e totais permanece a mesma
    discount = 0
    if db_cart.coupon and db_cart.coupon.is_valid:
        if db_cart.coupon.product_id is None:
            _, calculated_discount = apply_coupon(db_cart.coupon, subtotal)
            discount = calculated_discount

    total = subtotal - discount

    return CartSchema(
        id=db_cart.id,
        status=db_cart.status.value,
        coupon_code=db_cart.coupon_code,
        observation=db_cart.observation,
        items=cart_items_schemas,
        subtotal=subtotal,
        discount=discount,
        total=total
    )

# =====================================================================================
# SEÇÃO 2: EVENTOS SOCKET.IO
# =====================================================================================



@sio.event
async def get_or_create_cart(sid, data=None):
    """
    Busca o carrinho ativo de um cliente ou cria um novo.
    """
    print(f'[CART] Evento get_or_create_cart recebido do SID: {sid}')
    with get_db_manager() as db:
        try:

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

            # ✅ VERIFICA E REMOVE ITENS SEM ESTOQUE DO CARRINHO
            items_removed = []
            for cart_item in list(cart.items):  # Lista convertida para permitir remoção durante iteração
                product = db.query(models.Product).options(
                    selectinload(models.Product.variant_links)
                    .selectinload(models.ProductVariantLink.variant)
                    .selectinload(models.Variant.options)
                ).filter_by(id=cart_item.product_id).first()
                
                should_remove = False
                reason = ""
                
                if not product:
                    should_remove = True
                    reason = "produto não encontrado"
                elif not product.is_actually_available:
                    should_remove = True
                    reason = "produto sem estoque"
                elif product.control_stock and product.stock_quantity < cart_item.quantity:
                    should_remove = True
                    reason = f"estoque insuficiente (disponível: {product.stock_quantity}, solicitado: {cart_item.quantity})"
                else:
                    # Verifica estoque das variantes (complementos)
                    for cart_variant in cart_item.variants:
                        for cart_option in cart_variant.options:
                            variant_option = db.query(models.VariantOption).filter_by(
                                id=cart_option.variant_option_id
                            ).first()
                            
                            if variant_option and not variant_option.is_actually_available:
                                should_remove = True
                                reason = f"complemento '{variant_option.resolvedName}' sem estoque"
                                break
                            elif variant_option and variant_option.track_inventory:
                                total_quantity_needed = cart_option.quantity * cart_item.quantity
                                if variant_option.stock_quantity < total_quantity_needed:
                                    should_remove = True
                                    reason = f"complemento '{variant_option.resolvedName}' com estoque insuficiente"
                                    break
                        if should_remove:
                            break
                
                if should_remove:
                    print(f"🗑️ Removendo '{product.name if product else 'Produto desconhecido'}' do carrinho: {reason}")
                    items_removed.append(product.name if product else 'Produto desconhecido')
                    db.delete(cart_item)
            
            # Salva as remoções se houver
            if items_removed:
                db.commit()
                db.refresh(cart)
                print(f"✅ {len(items_removed)} itens removidos do carrinho")

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
            # 1. Validações Iniciais
            update_data = UpdateCartItemInput.model_validate(data)

            customer_session = db.query(models.CustomerSession).filter_by(sid=sid).first()
            if not customer_session or not customer_session.customer_id:
                return {'error': 'Usuário não autenticado na sessão.'}

            cart = _get_full_cart_query(db, customer_session.customer_id, customer_session.store_id)
            if not cart:
                cart = models.Cart(customer_id=customer_session.customer_id, store_id=customer_session.store_id)
                db.add(cart)
                db.flush()

            # 2. Validação das Regras de Negócio
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

            # ✅ --- MODO EDIÇÃO ---
            if cart_item_id_to_edit:
                print(f"📝 Modo Edição para o item ID: {cart_item_id_to_edit}")
                existing_item = db.query(models.CartItem).filter_by(id=cart_item_id_to_edit, cart_id=cart.id).first()

                if not existing_item:
                    return {'error': 'Item para editar não encontrado.'}

                if update_data.quantity <= 0:
                    db.delete(existing_item)
                else:
                    existing_item.quantity = update_data.quantity
                    existing_item.note = update_data.note or None  # ✅ Garante que string vazia vira None
                    existing_item.category_id = update_data.category_id
                    
                    # Remove variantes antigas
                    for old_variant in list(existing_item.variants):
                        db.delete(old_variant)
                    existing_item.variants.clear()
                    db.flush()
                    
                    # Adiciona novas variantes
                    if update_data.variants:
                        for variant_input in update_data.variants:
                            # ✅ CORREÇÃO: SQLAlchemy com Mapped precisa atribuir valores após criação
                            new_variant = models.CartItemVariant()
                            new_variant.cart_item_id = existing_item.id
                            new_variant.variant_id = variant_input.variant_id
                            new_variant.store_id = customer_session.store_id
                            db.add(new_variant)
                            db.flush()
                            
                            # Adiciona opções da variante
                            for option_input in variant_input.options:
                                if option_input.quantity > 0:
                                    # ✅ CORREÇÃO: SQLAlchemy com Mapped precisa atribuir valores após criação
                                    new_option = models.CartItemVariantOption()
                                    new_option.cart_item_variant_id = new_variant.id
                                    new_option.variant_option_id = option_input.variant_option_id
                                    new_option.quantity = option_input.quantity
                                    new_option.store_id = customer_session.store_id
                                    db.add(new_option)
                    
                    # Converte variants_input para formato de dicionário para fingerprint
                    variants_dict = []
                    if update_data.variants:
                        for variant_input in update_data.variants:
                            variant_dict = {
                                'variant_id': variant_input.variant_id,
                                'options': [
                                    {'variant_option_id': opt.variant_option_id}
                                    for opt in variant_input.options
                                    if opt.quantity > 0
                                ]
                            }
                            if variant_dict['options']:
                                variants_dict.append(variant_dict)
                    
                    existing_item.fingerprint = _get_item_fingerprint(
                        update_data.product_id,
                        update_data.category_id,
                        variants_dict,
                        update_data.note
                    )

            # ✅ --- MODO ADIÇÃO ---
            else:
                # Converte variants_input para formato de dicionário para fingerprint
                variants_dict = []
                if update_data.variants:
                    for variant_input in update_data.variants:
                        variant_dict = {
                            'variant_id': variant_input.variant_id,
                            'options': [
                                {'variant_option_id': opt.variant_option_id}
                                for opt in variant_input.options
                                if opt.quantity > 0
                            ]
                        }
                        if variant_dict['options']:
                            variants_dict.append(variant_dict)
                
                fingerprint = _get_item_fingerprint(
                    update_data.product_id,
                    update_data.category_id,
                    variants_dict,
                    update_data.note
                )

                existing_item = db.query(models.CartItem).filter_by(cart_id=cart.id,
                                                                    fingerprint=fingerprint).first()

                # ✅ LÓGICA CORRIGIDA AGORA ESTÁ DENTRO DO ELSE DO MODO ADIÇÃO
                if existing_item:
                    existing_item.quantity += update_data.quantity

                    if existing_item.quantity <= 0:
                        print(f"🗑️ Item (ID: {existing_item.id}) zerado. Removendo do carrinho.")
                        db.delete(existing_item)
                    else:
                        print(
                            f"🔄 Item idêntico (ID: {existing_item.id}) encontrado. Nova quantidade: {existing_item.quantity}.")
                        existing_item.note = update_data.note or None  # ✅ Garante que string vazia vira None
                        existing_item.category_id = update_data.category_id
                        
                        # Remove variantes antigas e adiciona novas (mesmo que seja idêntico, atualiza para garantir consistência)
                        for old_variant in list(existing_item.variants):
                            db.delete(old_variant)
                        existing_item.variants.clear()
                        db.flush()
                        
                        # Adiciona novas variantes
                        if update_data.variants:
                            for variant_input in update_data.variants:
                                # ✅ CORREÇÃO: SQLAlchemy com Mapped precisa atribuir valores após criação
                                new_variant = models.CartItemVariant()
                                new_variant.cart_item_id = existing_item.id
                                new_variant.variant_id = variant_input.variant_id
                                new_variant.store_id = customer_session.store_id
                                db.add(new_variant)
                                db.flush()
                                
                                # Adiciona opções da variante
                                for option_input in variant_input.options:
                                    if option_input.quantity > 0:
                                        # ✅ CORREÇÃO: SQLAlchemy com Mapped precisa atribuir valores após criação
                                        new_option = models.CartItemVariantOption()
                                        new_option.cart_item_variant_id = new_variant.id
                                        new_option.variant_option_id = option_input.variant_option_id
                                        new_option.quantity = option_input.quantity
                                        new_option.store_id = customer_session.store_id
                                        db.add(new_option)

                else:
                    if update_data.quantity > 0:
                        print(f"✨ Item novo (Fingerprint: {fingerprint}). Criando no carrinho.")
                        # ✅ CORREÇÃO: SQLAlchemy com Mapped precisa atribuir valores após criação
                        new_item = models.CartItem()
                        new_item.cart_id = cart.id
                        new_item.store_id = customer_session.store_id
                        new_item.product_id = update_data.product_id
                        new_item.category_id = update_data.category_id
                        new_item.quantity = update_data.quantity
                        new_item.note = update_data.note or None  # ✅ Garante que string vazia vira None
                        new_item.fingerprint = fingerprint
                        db.add(new_item)
                        db.flush()
                        
                        # Adiciona variantes para novo item
                        if update_data.variants:
                            for variant_input in update_data.variants:
                                # ✅ CORREÇÃO: SQLAlchemy com Mapped precisa atribuir valores após criação
                                new_variant = models.CartItemVariant()
                                new_variant.cart_item_id = new_item.id
                                new_variant.variant_id = variant_input.variant_id
                                new_variant.store_id = customer_session.store_id
                                db.add(new_variant)
                                db.flush()
                                
                                # Adiciona opções da variante
                                for option_input in variant_input.options:
                                    if option_input.quantity > 0:
                                        # ✅ CORREÇÃO: SQLAlchemy com Mapped precisa atribuir valores após criação
                                        new_option = models.CartItemVariantOption()
                                        new_option.cart_item_variant_id = new_variant.id
                                        new_option.variant_option_id = option_input.variant_option_id
                                        new_option.quantity = option_input.quantity
                                        new_option.store_id = customer_session.store_id
                                        db.add(new_option)

            # O commit fica no final para salvar qualquer uma das operações
            db.commit()
            
            # ✅ CORREÇÃO: Após commit, precisa fazer refresh do objeto cart em memória
            # para que os novos itens criados sejam refletidos
            db.refresh(cart)
            # Força o carregamento lazy dos itens (se necessário)
            _ = cart.items
            
            # ✅ CORREÇÃO ADICIONAL: Busca o carrinho novamente com eager loading
            # para garantir que todos os relacionamentos estejam carregados
            updated_cart = _get_full_cart_query(db, customer_session.customer_id, customer_session.store_id)
            
            if not updated_cart:
                return {'error': 'Erro ao buscar carrinho atualizado.'}
            
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