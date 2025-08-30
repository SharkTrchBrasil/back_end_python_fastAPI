from decimal import Decimal
from sqlalchemy.orm import Session, joinedload, selectinload
from src.core import models


# ✅ FUNÇÃO RENOMEADA E CORRIGIDA
def get_cashback_rule_for_order_item(order_item: models.OrderProduct) -> tuple[models.CashbackType, Decimal]:
    """
    Determina a regra de cashback a ser aplicada, seguindo a hierarquia: Produto > Categoria.
    Agora recebe o OrderProduct completo para ter o contexto da categoria.
    """
    product = order_item.product
    category = order_item.category  # Acessa a categoria através da nova relação

    # 1. Verifica regra específica no produto
    if product and product.cashback_type != models.CashbackType.NONE and product.cashback_value > 0:
        return product.cashback_type, product.cashback_value

    # 2. Se não, verifica a regra da categoria
    if category and category.cashback_type != models.CashbackType.NONE and category.cashback_value > 0:
        return category.cashback_type, category.cashback_value

    return models.CashbackType.NONE, Decimal('0.00')


def calculate_and_apply_cashback_for_order(order: models.Order, db: Session):
    """
    Calcula o cashback para um pedido, agora usando a lógica de cashback contextual.
    IMPORTANTE: A query que busca o 'order' para passar para esta função
    deve carregar as relações com 'selectinload' para evitar N+1 queries.
    Ex: .options(selectinload(models.Order.products).selectinload(models.OrderProduct.category))
    """
    if not order.customer_id or not order.customer:
        return

    total_cashback_generated_in_cents = 0

    for item in order.products:
        if not item.product:
            continue

        # O preço do item no pedido (item.price) já é o preço final (base + variantes).
        # Multiplicamos pela quantidade para ter o total do item.
        item_total_price_in_cents = item.price * item.quantity

        # ✅ CHAMA A FUNÇÃO CORRIGIDA, PASSANDO O ITEM INTEIRO
        rule_type, rule_value = get_cashback_rule_for_order_item(item)

        if rule_type == models.CashbackType.NONE:
            continue

        cashback_for_item_in_cents = 0

        if rule_type == models.CashbackType.PERCENTAGE:
            cashback_for_item_in_cents = (item_total_price_in_cents * int(rule_value)) // 100
        elif rule_type == models.CashbackType.FIXED:
            fixed_value_in_cents = int(rule_value * 100)
            cashback_for_item_in_cents = fixed_value_in_cents * item.quantity

        total_cashback_generated_in_cents += cashback_for_item_in_cents

    if total_cashback_generated_in_cents > 0:


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