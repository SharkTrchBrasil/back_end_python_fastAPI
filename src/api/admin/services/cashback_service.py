from decimal import Decimal
from sqlalchemy.orm import Session, joinedload, selectinload
from src.core import models


def get_cashback_rule_for_product(product: models.Product) -> tuple[models.CashbackType, Decimal]:
    """Determina a regra de cashback a ser aplicada, seguindo a hierarquia: Produto > Categoria."""
    # 1. Verifica regra específica no produto
    if product.cashback_type != models.CashbackType.NONE and product.cashback_value > 0:
        return product.cashback_type, product.cashback_value

    # 2. Se não, verifica a regra da categoria (requer que a relação product.category esteja carregada)
    if product.category and product.category.cashback_type != models.CashbackType.NONE and product.category.cashback_value > 0:
        return product.category.cashback_type, product.category.cashback_value

    return models.CashbackType.NONE, Decimal('0.00')


def calculate_and_apply_cashback_for_order(order: models.Order, db: Session):
    """
    Calcula o cashback para um pedido, considerando o preço total dos itens com suas variantes.
    Funciona com valores em CENTAVOS e só aplica se o pedido tiver um cliente.
    """
    # GUARDA DE SEGURANÇA: Só gera cashback para pedidos com cliente logado.
    if not order.customer_id or not order.customer:
        print(f"Pedido {order.id} não possui cliente, cashback não será gerado.")
        return

    total_cashback_generated_in_cents = 0

    for item in order.products:
        # PULA se o produto associado foi deletado ou não existe.
        if not item.product:
            continue

        # 1. CALCULA O PREÇO EFETIVO DO ITEM (BASE + VARIANTES)
        # O preço do item já inclui a quantidade, então calculamos o preço unitário efetivo
        item_base_price_in_cents = item.price
        variants_price_in_cents = sum(option.price for variant in item.variants for option in variant.options)

        effective_unit_price_in_cents = item_base_price_in_cents + variants_price_in_cents
        item_total_price_in_cents = effective_unit_price_in_cents * item.quantity

        # 2. OBTÉM A REGRA DE CASHBACK APLICÁVEL (Produto > Categoria)
        rule_type, rule_value = get_cashback_rule_for_product(item.product)

        if rule_type == models.CashbackType.NONE:
            continue

        cashback_for_item_in_cents = 0

        # 3. CALCULA O CASHBACK USANDO MATEMÁTICA DE INTEIROS
        if rule_type == models.CashbackType.PERCENTAGE:
            # rule_value é Decimal, ex: 5.00 para 5%. Multiplicamos e dividimos por 100.
            # Usamos // para garantir que o resultado seja um inteiro (centavos).
            cashback_for_item_in_cents = (item_total_price_in_cents * int(rule_value)) // 100
        elif rule_type == models.CashbackType.FIXED:
            # rule_value é um valor fixo em reais, ex: 5.00. Convertemos para centavos.
            fixed_value_in_cents = int(rule_value * 100)
            cashback_for_item_in_cents = fixed_value_in_cents * item.quantity

        total_cashback_generated_in_cents += cashback_for_item_in_cents

    if total_cashback_generated_in_cents > 0:
        # 4. APLICA OS VALORES E CRIA AS TRANSAÇÕES
        order.cashback_amount_generated = total_cashback_generated_in_cents

        new_transaction = models.CashbackTransaction(
            user_id=order.customer_id,
            order_id=order.id,
            # Salvamos o valor em Decimal na transação para consistência
            amount=Decimal(total_cashback_generated_in_cents) / 100,
            type="generated",
            description=f"Cashback gerado pelo pedido #{order.id}",
        )
        db.add(new_transaction)

        # O saldo do usuário também deve ser em Decimal para precisão
        order.customer.cashback_balance += Decimal(total_cashback_generated_in_cents) / 100