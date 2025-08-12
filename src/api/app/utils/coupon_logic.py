def apply_coupon(coupon, price_in_cents: int) -> tuple[int, int]:
    """
    Aplica um cupom a um preço em centavos.
    Retorna uma tupla: (novo_preço_em_centavos, valor_do_desconto_em_centavos).
    """
    if coupon.discount_type == 'percentage':
        discount_amount = int(price_in_cents * (coupon.discount_value / 100))
        new_price = price_in_cents - discount_amount
        return new_price, discount_amount
    elif coupon.discount_type == 'fixed':
        # Assumindo que o valor fixo no seu banco de dados já está em centavos
        discount_amount = int(coupon.discount_value)
        new_price = max(0, price_in_cents - discount_amount)
        return new_price, discount_amount

    # Se o tipo de cupom for desconhecido, não aplica desconto.
    return price_in_cents, 0